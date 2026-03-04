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

    issue = require_object(payload, "issue")
    issue_id = require_text(issue, "issue_id", "issue")
    change_targets = require_list_of_texts(issue, "change_targets", "issue")
    estimated_scope = require_text(issue, "estimated_scope", "issue")

    mismatch_reasons: list[str] = []
    if issue_id != scope_id:
        mismatch_reasons.append("issue_scope_mismatch")

    passed = len(mismatch_reasons) == 0
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "issue_id": issue_id,
        "change_targets": change_targets,
        "estimated_scope": estimated_scope,
        "mismatch_reasons": mismatch_reasons,
    }
    if not passed:
        result["errors"] = [
            error_dict("E_PROVIDER_FAILURE", "issue targets declaration check failed", "vcs")
        ]
    return result, passed


def main() -> int:
    args = parse_gate_args("Validate issue-change-targets-declared contract")
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
            "change_targets": ["invalid_input"],
            "estimated_scope": "unknown",
            "mismatch_reasons": ["invalid_input"],
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "vcs")],
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
