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
    require_text,
    write_result,
)


def _resolve_scope(request: dict[str, Any]) -> dict[str, Any]:
    request_id = require_text(request, "request_id")
    scope_id = require_text(request, "scope_id")
    run_id = require_text(request, "run_id")
    current_branch = require_text(request, "current_branch")
    head_sha = require_text(request, "head_sha")
    artifact_path = require_text(request, "artifact_path")
    expected_branch = optional_text(request, "expected_branch")
    base_sha = optional_text(request, "base_sha")

    mismatch_reasons: list[str] = []
    if expected_branch is not None and expected_branch != current_branch:
        mismatch_reasons.append("branch_mismatch")

    matched = len(mismatch_reasons) == 0
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "matched": matched,
        "current_branch": current_branch,
        "head_sha": head_sha,
        "mismatch_reasons": mismatch_reasons,
        "artifact_path": artifact_path,
    }
    if expected_branch is not None:
        result["expected_branch"] = expected_branch
    if base_sha is not None:
        result["base_sha"] = base_sha
    if not matched:
        result["errors"] = [error_dict("E_SCOPE_LOCK_FAILED", "scope lock mismatch", "stub-vcs")]
    return result


def _check_overlap(request: dict[str, Any]) -> dict[str, Any]:
    request_id = require_text(request, "request_id")
    scope_id = require_text(request, "scope_id")
    run_id = require_text(request, "run_id")
    artifact_path = require_text(request, "artifact_path")
    checked_scope_count = request.get("checked_scope_count", 0)
    if not isinstance(checked_scope_count, int) or checked_scope_count < 0:
        raise ValueError("invalid integer: checked_scope_count")

    overlaps = request.get("overlaps", [])
    if not isinstance(overlaps, list):
        raise ValueError("invalid list: overlaps")

    status = "pass" if len(overlaps) == 0 else "fail"
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "status": status,
        "artifact_path": artifact_path,
        "checked_scope_count": checked_scope_count,
        "overlaps": overlaps,
    }
    head_sha = optional_text(request, "head_sha")
    base_sha = optional_text(request, "base_sha")
    if head_sha is not None:
        result["head_sha"] = head_sha
    if base_sha is not None:
        result["base_sha"] = base_sha
    if status == "fail":
        result["errors"] = [error_dict("E_SCOPE_LOCK_FAILED", "overlap detected", "stub-vcs")]
    return result


def _create_or_update_pr(request: dict[str, Any]) -> dict[str, Any]:
    request_id = require_text(request, "request_id")
    scope_id = require_text(request, "scope_id")
    run_id = require_text(request, "run_id")
    pr_number = request.get("pr_number", 0)
    if not isinstance(pr_number, int) or pr_number < 0:
        raise ValueError("invalid integer: pr_number")
    return {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "status": "ready",
        "pr_number": pr_number,
        "pr_url": request.get("pr_url", ""),
    }


def _list_linked_branches(request: dict[str, Any]) -> dict[str, Any]:
    request_id = require_text(request, "request_id")
    scope_id = require_text(request, "scope_id")
    run_id = require_text(request, "run_id")
    branches = request.get("branches", [])
    if not isinstance(branches, list):
        raise ValueError("invalid list: branches")
    for value in branches:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("branches must contain non-empty strings")

    return {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "branches": branches,
    }


def run_operation(request: dict[str, Any]) -> dict[str, Any]:
    operation = require_text(request, "operation")
    if operation == "resolve_scope":
        return _resolve_scope(request)
    if operation == "check_overlap":
        return _check_overlap(request)
    if operation == "create_or_update_pr":
        return _create_or_update_pr(request)
    if operation == "list_linked_branches":
        return _list_linked_branches(request)
    raise ValueError("invalid operation")


def main() -> int:
    args = parse_gate_args("VCS adapter stub")

    output_path = Path(args.output) if args.output else None

    try:
        result = run_operation(read_json(Path(args.input)))
        exit_code = 0
    except ValueError as exc:
        result = {
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "stub-vcs")],
            "status": "invalid_input",
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
