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


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = _require_text(payload, "request_id")
    scope_id = _require_text(payload, "scope_id")
    run_id = _require_text(payload, "run_id")
    artifact_path = _require_text(payload, "artifact_path")

    estimate_approval = _require_object(payload, "estimate_approval")
    mode_selection = _require_object(payload, "mode_selection")

    estimate_status = _require_text(estimate_approval, "status", "estimate_approval").lower()
    estimate_artifact = _require_text(estimate_approval, "artifact_path", "estimate_approval")

    selected_mode = _require_text(mode_selection, "mode", "mode_selection").lower()
    reason = _require_text(mode_selection, "reason", "mode_selection")
    issue_id = _optional_text(mode_selection, "issue_id", "mode_selection")
    custom_contract_ref = _optional_text(mode_selection, "custom_contract_ref", "mode_selection")

    allowed_modes = {"impl", "tdd", "custom"}
    mismatch_reasons: list[str] = []
    if estimate_status != "approved":
        mismatch_reasons.append("estimate_not_approved")
    if selected_mode not in allowed_modes:
        mismatch_reasons.append("mode_not_allowed")
    if selected_mode == "custom" and custom_contract_ref is None:
        mismatch_reasons.append("custom_contract_ref_missing")
    if issue_id is not None and issue_id != scope_id:
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
        "selected_mode": selected_mode,
        "reason": reason,
        "estimate_approval": {
            "status": estimate_status,
            "artifact_path": estimate_artifact,
        },
        "mismatch_reasons": mismatch_reasons,
    }

    if issue_id is not None:
        result["issue_id"] = issue_id
    if custom_contract_ref is not None:
        result["custom_contract_ref"] = custom_contract_ref
    if head_sha is not None:
        result["head_sha"] = head_sha
    if base_sha is not None:
        result["base_sha"] = base_sha

    if not passed:
        result["errors"] = [_error("E_PROVIDER_FAILURE", "mode selection check failed")]
    return result, passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate mode selection contract")
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
            "selected_mode": "impl",
            "reason": "invalid_input",
            "estimate_approval": {
                "status": "pending",
                "artifact_path": "unknown",
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
