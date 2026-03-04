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


def _optional_text(obj: dict[str, Any], key: str) -> str | None:
    raw = obj.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"invalid string: {key}")
    return raw.strip()


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = _require_text(payload, "request_id")
    scope_id = _require_text(payload, "scope_id")
    run_id = _require_text(payload, "run_id")
    artifact_path = _require_text(payload, "artifact_path")

    expected = payload.get("expected")
    actual = payload.get("actual")
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        raise ValueError("expected and actual must be objects")

    expected_branch = _require_text(expected, "branch", "expected")
    current_branch = _require_text(actual, "branch", "actual")
    expected_head = _optional_text(expected, "head_sha")
    actual_head = _require_text(actual, "head_sha", "actual")
    expected_base = _optional_text(expected, "base_sha")
    actual_base = _optional_text(actual, "base_sha")
    expected_scope_ref = _optional_text(expected, "scope_ref")
    actual_scope_ref = _optional_text(actual, "scope_ref")

    mismatch_reasons: list[str] = []
    if expected_branch != current_branch:
        mismatch_reasons.append("branch_mismatch")
    if expected_head is not None and expected_head != actual_head:
        mismatch_reasons.append("head_sha_mismatch")
    if expected_base is not None:
        if actual_base is None:
            mismatch_reasons.append("base_sha_missing")
        elif expected_base != actual_base:
            mismatch_reasons.append("base_sha_mismatch")
    if (
        expected_scope_ref is not None
        and actual_scope_ref is not None
        and expected_scope_ref != actual_scope_ref
    ):
        mismatch_reasons.append("scope_ref_mismatch")

    matched = len(mismatch_reasons) == 0
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "matched": matched,
        "current_branch": current_branch,
        "expected_branch": expected_branch,
        "head_sha": actual_head,
        "mismatch_reasons": mismatch_reasons,
        "artifact_path": artifact_path,
    }
    if actual_base is not None:
        result["base_sha"] = actual_base
    if not matched:
        result["errors"] = [_error("E_SCOPE_LOCK_FAILED", "scope lock mismatch")]
    return result, matched


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate scope lock contract")
    parser.add_argument("--input", required=True, help="Path to input JSON")
    parser.add_argument("--output", help="Path to write result JSON")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else None

    try:
        payload = _read_json(Path(args.input))
        result, matched = _build_result(payload)
        exit_code = 0 if matched else 2
    except ValueError as exc:
        result = {
            "request_id": "unknown",
            "scope_id": "unknown",
            "run_id": "unknown",
            "matched": False,
            "current_branch": "unknown",
            "head_sha": "unknown",
            "mismatch_reasons": ["invalid_input"],
            "artifact_path": "unknown",
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
