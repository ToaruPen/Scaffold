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


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = require_text(payload, "request_id")
    scope_id = require_text(payload, "scope_id")
    run_id = require_text(payload, "run_id")
    artifact_path = require_text(payload, "artifact_path")

    expected = payload.get("expected")
    actual = payload.get("actual")
    if not isinstance(expected, dict) or not isinstance(actual, dict):
        raise ValueError("expected and actual must be objects")

    expected_branch = require_text(expected, "branch", "expected")
    current_branch = require_text(actual, "branch", "actual")
    expected_head = optional_text(expected, "head_sha")
    actual_head = require_text(actual, "head_sha", "actual")
    expected_base = optional_text(expected, "base_sha")
    actual_base = optional_text(actual, "base_sha")
    expected_scope_ref = optional_text(expected, "scope_ref")
    actual_scope_ref = optional_text(actual, "scope_ref")

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
        result["errors"] = [error_dict("E_SCOPE_LOCK_FAILED", "scope lock mismatch", "vcs")]
    return result, matched


def main() -> int:
    args = parse_gate_args("Validate scope lock contract")
    output_path = Path(args.output) if args.output else None

    try:
        payload = read_json(Path(args.input))
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
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "vcs")],
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
