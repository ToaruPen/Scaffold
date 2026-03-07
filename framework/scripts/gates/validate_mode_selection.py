#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from framework.scripts.lib.gate_helpers import (
    error_dict,
    optional_text,
    parse_gate_args,
    read_json,
    require_object,
    require_text,
    write_result,
)


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = require_text(payload, "request_id")
    scope_id = require_text(payload, "scope_id")
    run_id = require_text(payload, "run_id")
    artifact_path = require_text(payload, "artifact_path")

    estimate_approval = require_object(payload, "estimate_approval")
    mode_selection = require_object(payload, "mode_selection")

    estimate_status = require_text(estimate_approval, "status", "estimate_approval").lower()
    estimate_artifact = require_text(estimate_approval, "artifact_path", "estimate_approval")

    selected_mode = require_text(mode_selection, "mode", "mode_selection").lower()
    reason = require_text(mode_selection, "reason", "mode_selection")
    issue_id = optional_text(mode_selection, "issue_id", "mode_selection")
    custom_contract_ref = optional_text(mode_selection, "custom_contract_ref", "mode_selection")

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

    head_sha = optional_text(payload, "head_sha")
    base_sha = optional_text(payload, "base_sha")

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
        result["errors"] = [error_dict("E_PROVIDER_FAILURE", "mode selection check failed", "vcs")]
    return result, passed


def main() -> int:
    args = parse_gate_args("Validate mode selection contract")
    output_path = Path(args.output) if args.output else None

    try:
        payload = read_json(Path(args.input))
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
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "vcs")],
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
