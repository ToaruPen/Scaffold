#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_REVIEW_STAGE_KEYS = ("review_cycle", "final_review")
REQUIRED_GATE_STAGE_KEYS = ("drift_detection", "adr_index")


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "retryable": False,
        "provider": "vcs",
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"failed to read input JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    return data


def _require_text(obj: dict[str, Any], key: str, parent: str = "") -> str:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"missing or invalid string: {prefix}{key}")
    return raw.strip()


def _optional_text(obj: dict[str, Any], key: str, parent: str = "") -> str | None:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"invalid string: {prefix}{key}")
    return raw.strip()


def _require_object(obj: dict[str, Any], key: str) -> dict[str, Any]:
    raw = obj.get(key)
    if not isinstance(raw, dict):
        raise ValueError(f"missing or invalid object: {key}")
    return raw


def _validate_stage(
    *,
    stage_key: str,
    stage_obj: dict[str, Any],
    expected_head: str,
    expected_base: str | None,
    mismatch_reasons: list[str],
) -> dict[str, str]:
    stage_status = _require_text(stage_obj, "status", f"review_evidence.{stage_key}").lower()
    stage_head = _require_text(stage_obj, "head_sha", f"review_evidence.{stage_key}")
    stage_base = _optional_text(stage_obj, "base_sha", f"review_evidence.{stage_key}")
    stage_artifact = _require_text(stage_obj, "artifact_path", f"review_evidence.{stage_key}")

    if stage_status != "pass":
        mismatch_reasons.append(f"{stage_key}_not_passed")
    if stage_head != expected_head:
        mismatch_reasons.append(f"{stage_key}_head_sha_mismatch")
    if expected_base is not None:
        if stage_base is None:
            mismatch_reasons.append(f"{stage_key}_base_sha_missing")
        elif stage_base != expected_base:
            mismatch_reasons.append(f"{stage_key}_base_sha_mismatch")

    result = {
        "status": stage_status,
        "head_sha": stage_head,
        "artifact_path": stage_artifact,
    }
    if stage_base is not None:
        result["base_sha"] = stage_base
    return result


def _validate_gate_stage(
    *,
    stage_key: str,
    stage_obj: dict[str, Any],
    mismatch_reasons: list[str],
) -> dict[str, str]:
    raw_stage_status = _require_text(stage_obj, "status", f"review_evidence.{stage_key}").lower()
    stage_status = "pass" if raw_stage_status == "pass" else "fail"
    stage_artifact = _require_text(stage_obj, "artifact_path", f"review_evidence.{stage_key}")
    if stage_status != "pass":
        mismatch_reasons.append(f"{stage_key}_not_passed")
    return {
        "status": stage_status,
        "artifact_path": stage_artifact,
    }


def _missing_gate_stage_result() -> dict[str, str]:
    return {
        "status": "fail",
        "artifact_path": "unknown",
    }


def _scope_lock_mismatch_reasons(
    *,
    scope_lock_matched: bool,
    scope_lock_head: str,
    scope_lock_base: str | None,
    expected_head: str,
    expected_base: str | None,
) -> list[str]:
    mismatch_reasons: list[str] = []
    if not scope_lock_matched:
        mismatch_reasons.append("scope_lock_not_matched")
    if scope_lock_head != expected_head:
        mismatch_reasons.append("scope_lock_head_sha_mismatch")
    if expected_base is not None:
        if scope_lock_base is None:
            mismatch_reasons.append("scope_lock_base_sha_missing")
        elif scope_lock_base != expected_base:
            mismatch_reasons.append("scope_lock_base_sha_mismatch")
    return mismatch_reasons


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = _require_text(payload, "request_id")
    scope_id = _require_text(payload, "scope_id")
    run_id = _require_text(payload, "run_id")
    artifact_path = _require_text(payload, "artifact_path")

    expected = _require_object(payload, "expected")
    expected_head = _require_text(expected, "head_sha", "expected")
    expected_base = _optional_text(expected, "base_sha", "expected")

    scope_lock = _require_object(payload, "scope_lock")
    scope_lock_matched = scope_lock.get("matched")
    if not isinstance(scope_lock_matched, bool):
        raise ValueError("missing or invalid boolean: scope_lock.matched")
    scope_lock_head = _require_text(scope_lock, "head_sha", "scope_lock")
    scope_lock_base = _optional_text(scope_lock, "base_sha", "scope_lock")

    review_evidence = _require_object(payload, "review_evidence")

    mismatch_reasons = _scope_lock_mismatch_reasons(
        scope_lock_matched=scope_lock_matched,
        scope_lock_head=scope_lock_head,
        scope_lock_base=scope_lock_base,
        expected_head=expected_head,
        expected_base=expected_base,
    )

    stage_results: dict[str, dict[str, str]] = {}
    for stage_key in REQUIRED_REVIEW_STAGE_KEYS:
        stage_obj = review_evidence.get(stage_key)
        if not isinstance(stage_obj, dict):
            mismatch_reasons.append(f"{stage_key}_missing")
            continue
        stage_results[stage_key] = _validate_stage(
            stage_key=stage_key,
            stage_obj=stage_obj,
            expected_head=expected_head,
            expected_base=expected_base,
            mismatch_reasons=mismatch_reasons,
        )
    for stage_key in REQUIRED_GATE_STAGE_KEYS:
        stage_obj = review_evidence.get(stage_key)
        if not isinstance(stage_obj, dict):
            mismatch_reasons.append(f"{stage_key}_missing")
            stage_results[stage_key] = _missing_gate_stage_result()
            continue
        stage_results[stage_key] = _validate_gate_stage(
            stage_key=stage_key,
            stage_obj=stage_obj,
            mismatch_reasons=mismatch_reasons,
        )

    passed = len(mismatch_reasons) == 0
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "scope_lock": {
            "matched": scope_lock_matched,
            "head_sha": scope_lock_head,
        },
        "review_evidence": stage_results,
        "head_sha": expected_head,
        "mismatch_reasons": mismatch_reasons,
    }
    if expected_base is not None:
        result["base_sha"] = expected_base
    if scope_lock_base is not None:
        result["scope_lock"]["base_sha"] = scope_lock_base

    if not passed:
        result["errors"] = [_error("E_PROVIDER_FAILURE", "pr preconditions check failed")]
    return result, passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate PR preconditions contract")
    parser.add_argument("--input", required=True, help="Path to input JSON")
    parser.add_argument("--output", help="Path to write result JSON")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else None

    try:
        payload = _read_json(Path(args.input))
        result, passed = _build_result(payload)
        exit_code = 0 if passed else 2
    except ValueError as exc:
        result = {
            "request_id": "unknown",
            "scope_id": "unknown",
            "run_id": "unknown",
            "status": "fail",
            "artifact_path": "unknown",
            "scope_lock": {
                "matched": False,
                "head_sha": "unknown",
            },
            "review_evidence": {},
            "head_sha": "unknown",
            "mismatch_reasons": ["invalid_input"],
            "errors": [_error("E_INPUT_INVALID", str(exc))],
        }
        exit_code = 2

    output_text = json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
    print(output_text, end="")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
