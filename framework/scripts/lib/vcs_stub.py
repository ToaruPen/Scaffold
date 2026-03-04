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
        "provider": "stub-vcs",
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


def _optional_text(obj: dict[str, Any], key: str) -> str | None:
    raw = obj.get(key)
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"invalid string: {key}")
    return raw.strip()


def _require_bool(obj: dict[str, Any], key: str) -> bool:
    raw = obj.get(key)
    if not isinstance(raw, bool):
        raise ValueError(f"missing or invalid boolean: {key}")
    return raw


def _resolve_scope(request: dict[str, Any]) -> dict[str, Any]:
    request_id = _require_text(request, "request_id")
    scope_id = _require_text(request, "scope_id")
    run_id = _require_text(request, "run_id")
    current_branch = _require_text(request, "current_branch")
    head_sha = _require_text(request, "head_sha")
    artifact_path = _require_text(request, "artifact_path")
    expected_branch = _optional_text(request, "expected_branch")
    base_sha = _optional_text(request, "base_sha")

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
        result["errors"] = [_error("E_SCOPE_LOCK_FAILED", "scope lock mismatch")]
    return result


def _check_overlap(request: dict[str, Any]) -> dict[str, Any]:
    request_id = _require_text(request, "request_id")
    scope_id = _require_text(request, "scope_id")
    run_id = _require_text(request, "run_id")
    artifact_path = _require_text(request, "artifact_path")
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
    head_sha = _optional_text(request, "head_sha")
    base_sha = _optional_text(request, "base_sha")
    if head_sha is not None:
        result["head_sha"] = head_sha
    if base_sha is not None:
        result["base_sha"] = base_sha
    if status == "fail":
        result["errors"] = [_error("E_SCOPE_LOCK_FAILED", "overlap detected")]
    return result


def _create_or_update_pr(request: dict[str, Any]) -> dict[str, Any]:
    request_id = _require_text(request, "request_id")
    scope_id = _require_text(request, "scope_id")
    run_id = _require_text(request, "run_id")
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
    request_id = _require_text(request, "request_id")
    scope_id = _require_text(request, "scope_id")
    run_id = _require_text(request, "run_id")
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
    operation = _require_text(request, "operation")
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
    parser = argparse.ArgumentParser(description="VCS adapter stub")
    parser.add_argument("--input", required=True, help="Path to input JSON")
    parser.add_argument("--output", help="Path to write output JSON")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else None

    try:
        result = run_operation(_read_json(Path(args.input)))
        exit_code = 0
    except ValueError as exc:
        result = {
            "errors": [_error("E_INPUT_INVALID", str(exc))],
            "status": "invalid_input",
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
