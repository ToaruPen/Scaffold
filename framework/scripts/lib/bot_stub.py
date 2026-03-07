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


def _require_int(obj: dict[str, Any], key: str) -> int:
    raw = obj.get(key)
    if not isinstance(raw, int) or raw < 1:
        raise ValueError(f"missing or invalid integer: {key}")
    return raw


def _request_review(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": require_text(request, "request_id"),
        "scope_id": require_text(request, "scope_id"),
        "run_id": require_text(request, "run_id"),
        "provider": "stub-bot",
        "status": "queued",
    }


def _fetch_feedback(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "provider": "stub-bot",
        "pr_number": _require_int(request, "pr_number"),
        "cycle": _require_int(request, "cycle"),
        "status": "no_findings",
        "findings": [],
        "provider_metadata": {
            "provider": "stub-bot",
            "mode": "deterministic",
        },
    }


def _mark_addressed(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": require_text(request, "request_id"),
        "scope_id": require_text(request, "scope_id"),
        "run_id": require_text(request, "run_id"),
        "provider": "stub-bot",
        "status": "acknowledged",
    }


def run_operation(request: dict[str, Any]) -> dict[str, Any]:
    operation = require_text(request, "operation")
    if operation == "request_review":
        return _request_review(request)
    if operation == "fetch_feedback":
        return _fetch_feedback(request)
    if operation == "mark_addressed":
        return _mark_addressed(request)
    raise ValueError("invalid operation")


def main() -> int:
    args = parse_gate_args("Bot adapter stub")

    output_path = Path(args.output) if args.output else None

    try:
        result = run_operation(read_json(Path(args.input)))
        exit_code = 0
    except ValueError as exc:
        result = {
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "stub-bot")],
            "status": "invalid_input",
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
