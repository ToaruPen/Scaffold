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

    waiver = require_object(payload, "waiver")
    gate_id = require_text(waiver, "gate_id", "waiver")
    reason = require_text(waiver, "reason", "waiver")
    approved_by = require_text(waiver, "approved_by", "waiver")
    approved_at = require_text(waiver, "approved_at", "waiver")
    expiry = optional_text(waiver, "expiry", "waiver")
    scope_restriction = optional_text(waiver, "scope_restriction", "waiver")

    mismatch_reasons: list[str] = []
    if scope_restriction is not None and scope_restriction.startswith("scope:"):
        restricted_scope = scope_restriction.split(":", 1)[1].strip()
        if restricted_scope and restricted_scope != scope_id:
            mismatch_reasons.append("scope_restriction_mismatch")
    passed = len(mismatch_reasons) == 0
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "gate_id": gate_id,
        "reason": reason,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "mismatch_reasons": mismatch_reasons,
    }
    if expiry is not None:
        result["expiry"] = expiry
    if scope_restriction is not None:
        result["scope_restriction"] = scope_restriction
    if not passed:
        result["errors"] = [error_dict("E_PROVIDER_FAILURE", "waiver check failed", "vcs")]
    return result, passed


def main() -> int:
    args = parse_gate_args("Validate waiver-exception contract")
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
            "gate_id": "unknown",
            "reason": "invalid_input",
            "approved_by": "unknown",
            "approved_at": "unknown",
            "mismatch_reasons": ["invalid_input"],
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "vcs")],
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
