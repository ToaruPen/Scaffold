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


def _require_text(obj: dict[str, Any], key: str) -> str:
    raw = obj.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"missing or invalid string: {key}")
    return raw.strip()


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
        other_scope_id = _require_text(scope, "scope_id")
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
        other_scope_id = _require_text(scope, "scope_id")
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
    request_id = _require_text(payload, "request_id")
    scope_id = _require_text(payload, "scope_id")
    run_id = _require_text(payload, "run_id")
    artifact_path = _require_text(payload, "artifact_path")

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
        result["errors"] = [_error("E_SCOPE_LOCK_FAILED", "overlap detected across active scopes")]
    return result, passed


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate overlap safety contract")
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
            "checked_scope_count": 0,
            "overlaps": [],
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
