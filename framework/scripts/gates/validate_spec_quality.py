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
    require_object,
    require_text,
    write_result,
)


def _require_bool(obj: dict[str, Any], key: str, parent: str = "") -> bool:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if not isinstance(raw, bool):
        raise ValueError(f"missing or invalid boolean: {prefix}{key}")
    return raw


def _require_int(obj: dict[str, Any], key: str, parent: str = "") -> int:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if not isinstance(raw, int):
        raise ValueError(f"missing or invalid integer: {prefix}{key}")
    return raw


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = require_text(payload, "request_id")
    scope_id = require_text(payload, "scope_id")
    run_id = require_text(payload, "run_id")
    artifact_path = require_text(payload, "artifact_path")

    spec = require_object(payload, "spec")
    spec_ref = require_text(spec, "artifact_ref", "spec")
    has_acceptance_criteria = _require_bool(spec, "has_acceptance_criteria", "spec")
    has_out_of_scope = _require_bool(spec, "has_out_of_scope", "spec")
    acceptance_criteria_count = _require_int(spec, "acceptance_criteria_count", "spec")

    mismatch_reasons: list[str] = []
    if not has_acceptance_criteria:
        mismatch_reasons.append("acceptance_criteria_missing")
    if not has_out_of_scope:
        mismatch_reasons.append("out_of_scope_missing")
    if acceptance_criteria_count < 1:
        mismatch_reasons.append("acceptance_criteria_count_invalid")

    passed = len(mismatch_reasons) == 0
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "spec_ref": spec_ref,
        "has_acceptance_criteria": has_acceptance_criteria,
        "has_out_of_scope": has_out_of_scope,
        "acceptance_criteria_count": acceptance_criteria_count,
        "mismatch_reasons": mismatch_reasons,
    }
    if not passed:
        result["errors"] = [
            error_dict("E_PROVIDER_FAILURE", "spec quality minimum check failed", "vcs")
        ]
    return result, passed


def main() -> int:
    args = parse_gate_args("Validate spec-quality-minimum contract")
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
            "spec_ref": "unknown",
            "has_acceptance_criteria": False,
            "has_out_of_scope": False,
            "acceptance_criteria_count": 0,
            "mismatch_reasons": ["invalid_input"],
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "vcs")],
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
