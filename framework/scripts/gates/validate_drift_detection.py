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
    require_text,
    write_result,
)

_MISSING_DECLARED_TARGETS_SENTINEL = "__missing_declared_targets__"


def _matches_target(target: str, changed_path: str) -> bool:
    normalized_target = target.strip()
    normalized_path = changed_path.strip()
    if normalized_target == normalized_path:
        return True

    target_dir = normalized_target[:-1] if normalized_target.endswith("/") else normalized_target
    return bool(normalized_path.startswith(f"{target_dir}/"))


def _require_actual_changes_allow_empty(payload: dict[str, Any]) -> list[str]:
    raw = payload.get("actual_changes")
    if not isinstance(raw, list):
        raise ValueError("missing or invalid list: actual_changes")

    values: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("invalid string element: actual_changes")
        values.append(item.strip())
    return values


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = require_text(payload, "request_id")
    scope_id = require_text(payload, "scope_id")
    run_id = require_text(payload, "run_id")
    artifact_path = require_text(payload, "artifact_path")
    declared_targets = require_list_of_texts(payload, "declared_targets")
    actual_changes = _require_actual_changes_allow_empty(payload)

    undeclared_additions: list[str] = []
    for changed_path in actual_changes:
        if not any(_matches_target(target, changed_path) for target in declared_targets):
            undeclared_additions.append(changed_path)

    unused_declarations: list[str] = []
    for target in declared_targets:
        if not any(_matches_target(target, changed_path) for changed_path in actual_changes):
            unused_declarations.append(target)

    mismatch_reasons: list[str] = []
    missing_declaration_evidence = _MISSING_DECLARED_TARGETS_SENTINEL in declared_targets
    if missing_declaration_evidence:
        mismatch_reasons.append("missing_declared_targets")
    if undeclared_additions:
        mismatch_reasons.append("undeclared_change_detected")

    passed = len(undeclared_additions) == 0 and not missing_declaration_evidence
    sanitized_unused_declarations = [
        target for target in unused_declarations if target != _MISSING_DECLARED_TARGETS_SENTINEL
    ]
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "declared_targets": declared_targets,
        "actual_changes": actual_changes,
        "undeclared_additions": undeclared_additions,
        "unused_declarations": sanitized_unused_declarations,
        "mismatch_reasons": mismatch_reasons,
    }
    if not passed:
        result["errors"] = [error_dict("E_PROVIDER_FAILURE", "drift detection check failed", "vcs")]
    return result, passed


def main() -> int:
    args = parse_gate_args("Validate drift-detection contract")
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
            "declared_targets": ["invalid_input"],
            "actual_changes": ["invalid_input"],
            "undeclared_additions": [],
            "unused_declarations": [],
            "mismatch_reasons": ["invalid_input"],
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "vcs")],
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
