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


def _require_list_of_texts(obj: dict[str, Any], key: str, parent: str) -> list[str]:
    raw = obj.get(key)
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"missing or invalid non-empty list: {parent}.{key}")
    values: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"invalid string element: {parent}.{key}")
        values.append(item.strip())
    return values


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = _require_text(payload, "request_id")
    scope_id = _require_text(payload, "scope_id")
    run_id = _require_text(payload, "run_id")
    artifact_path = _require_text(payload, "artifact_path")

    estimate = _require_object(payload, "estimate")
    approval = _require_object(payload, "approval")

    issue_id = _require_text(estimate, "issue_id", "estimate")
    estimate_ref = _require_text(estimate, "estimate_ref", "estimate")
    assumptions = _require_list_of_texts(estimate, "assumptions", "estimate")

    approval_status = _require_text(approval, "status", "approval").lower()
    approved_by = _require_text(approval, "approved_by", "approval")
    approved_at = _require_text(approval, "approved_at", "approval")
    decision_id = _require_text(approval, "decision_id", "approval")

    mismatch_reasons: list[str] = []
    if approval_status != "approved":
        mismatch_reasons.append("estimate_not_approved")
    if issue_id != scope_id:
        mismatch_reasons.append("issue_scope_mismatch")

    head_sha = _optional_text(payload, "head_sha")
    base_sha = _optional_text(payload, "base_sha")

    passed = len(mismatch_reasons) == 0
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "issue_id": issue_id,
        "estimate_ref": estimate_ref,
        "assumptions": assumptions,
        "approval": {
            "status": approval_status,
            "approved_by": approved_by,
            "approved_at": approved_at,
            "decision_id": decision_id,
        },
        "mismatch_reasons": mismatch_reasons,
    }

    if head_sha is not None:
        result["head_sha"] = head_sha
    if base_sha is not None:
        result["base_sha"] = base_sha

    if not passed:
        result["errors"] = [_error("E_PROVIDER_FAILURE", "estimate approval check failed")]
    return result, passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate estimate approval contract")
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
            "issue_id": "unknown",
            "estimate_ref": "unknown",
            "assumptions": ["invalid_input"],
            "approval": {
                "status": "pending",
                "approved_by": "unknown",
                "approved_at": "unknown",
                "decision_id": "unknown",
            },
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
