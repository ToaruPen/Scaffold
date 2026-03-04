#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "retryable": False,
        "provider": "review_engine",
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


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = _require_text(payload, "request_id")
    scope_id = _require_text(payload, "scope_id")
    run_id = _require_text(payload, "run_id")
    artifact_path = _require_text(payload, "artifact_path")

    expected = _require_object(payload, "expected")
    review = _require_object(payload, "review")
    evidence = _require_object(review, "evidence")

    expected_head = _require_text(expected, "head_sha", "expected")
    expected_base = _optional_text(expected, "base_sha", "expected")

    review_status = _require_text(review, "status", "review").lower()
    review_summary = _require_text(review, "summary", "review")
    evidence_head = _require_text(evidence, "head_sha", "review.evidence")
    evidence_base = _optional_text(evidence, "base_sha", "review.evidence")
    evidence_artifact = _require_text(evidence, "artifact_path", "review.evidence")

    mismatch_reasons: list[str] = []
    if review_status not in {"approved", "approved_with_nits"}:
        mismatch_reasons.append("review_not_approved")
    if expected_head != evidence_head:
        mismatch_reasons.append("head_sha_mismatch")
    if expected_base is not None:
        if evidence_base is None:
            mismatch_reasons.append("base_sha_missing")
        elif expected_base != evidence_base:
            mismatch_reasons.append("base_sha_mismatch")
    if artifact_path != evidence_artifact:
        mismatch_reasons.append("artifact_path_mismatch")

    passed = len(mismatch_reasons) == 0
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "stage": "test-review",
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "review_status": review_status,
        "summary": review_summary,
        "head_sha": evidence_head,
        "mismatch_reasons": mismatch_reasons,
    }
    if evidence_base is not None:
        result["base_sha"] = evidence_base
    if not passed:
        result["errors"] = [_error("E_PROVIDER_FAILURE", "test-review evidence check failed")]
    return result, passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate test-review evidence contract")
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
            "stage": "test-review",
            "status": "fail",
            "artifact_path": "unknown",
            "review_status": "blocked",
            "summary": "invalid_input",
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
