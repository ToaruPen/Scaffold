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
        "provider": "stub-bot",
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


def _require_int(obj: dict[str, Any], key: str) -> int:
    raw = obj.get(key)
    if not isinstance(raw, int) or raw < 1:
        raise ValueError(f"missing or invalid integer: {key}")
    return raw


def _request_review(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": _require_text(request, "request_id"),
        "scope_id": _require_text(request, "scope_id"),
        "run_id": _require_text(request, "run_id"),
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
        "request_id": _require_text(request, "request_id"),
        "scope_id": _require_text(request, "scope_id"),
        "run_id": _require_text(request, "run_id"),
        "provider": "stub-bot",
        "status": "acknowledged",
    }


def run_operation(request: dict[str, Any]) -> dict[str, Any]:
    operation = _require_text(request, "operation")
    if operation == "request_review":
        return _request_review(request)
    if operation == "fetch_feedback":
        return _fetch_feedback(request)
    if operation == "mark_addressed":
        return _mark_addressed(request)
    raise ValueError("invalid operation")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bot adapter stub")
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
