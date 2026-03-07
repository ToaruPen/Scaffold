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
    require_text,
    write_result,
)


def _normalize_targets(values: object, key_name: str) -> set[str]:
    if not isinstance(values, list) or not values:
        raise ValueError(f"missing or invalid non-empty list: {key_name}")
    normalized: set[str] = set()
    for item in values:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"invalid target path in {key_name}")
        normalized.add(item.strip())
    return normalized


def _waiver_pairs(scope: dict[str, Any]) -> set[str]:
    allow = scope.get("allow_overlap_with")
    if allow is None:
        return set()
    if not isinstance(allow, list):
        raise ValueError("allow_overlap_with must be a list when present")
    values: set[str] = set()
    for item in allow:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("allow_overlap_with values must be non-empty strings")
        values.add(item.strip())
    return values


def _active_scope_entries(active_scopes_raw: object, current_scope_id: str) -> list[dict[str, Any]]:
    if not isinstance(active_scopes_raw, list):
        raise ValueError("active_scopes must be a list")

    active_entries: list[dict[str, Any]] = []
    closed_statuses = {"closed", "done", "merged", "cancelled"}

    for scope in active_scopes_raw:
        if not isinstance(scope, dict):
            raise ValueError("each active scope must be an object")
        other_scope_id = require_text(scope, "scope_id")
        if other_scope_id == current_scope_id:
            continue
        status = str(scope.get("status", "active")).strip().lower()
        if status in closed_statuses:
            continue
        active_entries.append(scope)

    return active_entries


def _collect_overlaps(
    *,
    scope_id: str,
    current_targets: set[str],
    current_allow: set[str],
    active_scopes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    overlaps: list[dict[str, Any]] = []
    checked_scope_count = 0

    for scope in active_scopes:
        other_scope_id = require_text(scope, "scope_id")
        other_targets = _normalize_targets(
            scope.get("targets"), f"active_scopes[{other_scope_id}].targets"
        )
        other_allow = _waiver_pairs(scope)
        checked_scope_count += 1

        if other_scope_id in current_allow or scope_id in other_allow:
            continue

        collision = sorted(current_targets.intersection(other_targets))
        if collision:
            overlaps.append({"scope_id": other_scope_id, "paths": collision})

    return overlaps, checked_scope_count


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = require_text(payload, "request_id")
    scope_id = require_text(payload, "scope_id")
    run_id = require_text(payload, "run_id")
    artifact_path = require_text(payload, "artifact_path")

    current_targets = _normalize_targets(payload.get("current_targets"), "current_targets")
    current_allow = _waiver_pairs(payload)

    active_scopes = _active_scope_entries(payload.get("active_scopes"), scope_id)
    overlaps, checked_scope_count = _collect_overlaps(
        scope_id=scope_id,
        current_targets=current_targets,
        current_allow=current_allow,
        active_scopes=active_scopes,
    )

    passed = len(overlaps) == 0
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "checked_scope_count": checked_scope_count,
        "overlaps": overlaps,
    }

    head_sha = payload.get("head_sha")
    base_sha = payload.get("base_sha")
    if isinstance(head_sha, str) and head_sha.strip():
        result["head_sha"] = head_sha.strip()
    if isinstance(base_sha, str) and base_sha.strip():
        result["base_sha"] = base_sha.strip()

    if not passed:
        result["errors"] = [
            error_dict("E_SCOPE_LOCK_FAILED", "overlap detected across active scopes", "vcs")
        ]
    return result, passed


def main() -> int:
    args = parse_gate_args("Validate overlap safety contract")
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
            "checked_scope_count": 0,
            "overlaps": [],
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "vcs")],
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
