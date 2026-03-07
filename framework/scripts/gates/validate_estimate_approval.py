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
    require_list_of_texts,
    require_object,
    require_text,
    write_result,
)


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = require_text(payload, "request_id")
    scope_id = require_text(payload, "scope_id")
    run_id = require_text(payload, "run_id")
    artifact_path = require_text(payload, "artifact_path")

    estimate = require_object(payload, "estimate")
    approval = require_object(payload, "approval")

    issue_id = require_text(estimate, "issue_id", "estimate")
    estimate_ref = require_text(estimate, "estimate_ref", "estimate")
    assumptions = require_list_of_texts(estimate, "assumptions", "estimate")

    approval_status = require_text(approval, "status", "approval").lower()
    approved_by = require_text(approval, "approved_by", "approval")
    approved_at = require_text(approval, "approved_at", "approval")
    decision_id = require_text(approval, "decision_id", "approval")

    mismatch_reasons: list[str] = []
    if approval_status != "approved":
        mismatch_reasons.append("estimate_not_approved")
    if issue_id != scope_id:
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
        result["errors"] = [
            error_dict("E_PROVIDER_FAILURE", "estimate approval check failed", "vcs")
        ]
    return result, passed


def main() -> int:
    args = parse_gate_args("Validate estimate approval contract")
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
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "vcs")],
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
