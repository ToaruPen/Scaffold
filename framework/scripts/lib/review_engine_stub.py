#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _error(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "retryable": False,
        "provider": "stub-review-engine",
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


def run_review(request: dict[str, Any]) -> dict[str, Any]:
    request_id = _require_text(request, "request_id")
    scope_id = _require_text(request, "scope_id")
    run_id = _require_text(request, "run_id")
    _require_text(request, "diff_mode")
    head_sha = _require_text(request, "head_sha")
    base_sha = _optional_text(request, "base_sha")
    _require_text(request, "review_goal")
    _require_text(request, "schema_version")

    artifact_path = f"artifacts/reviews/{scope_id}/{run_id}/review-engine-stub.json"
    evidence: dict[str, Any] = {
        "head_sha": head_sha,
        "artifact_path": artifact_path,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    if base_sha is not None:
        evidence["base_sha"] = base_sha

    return {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "status": "approved",
        "summary": "stub review approved",
        "findings": [],
        "evidence": evidence,
        "provider_metadata": {
            "provider": "stub-review-engine",
            "model": "deterministic-stub",
            "duration_ms": 0,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review engine adapter stub")
    parser.add_argument("--input", required=True, help="Path to input JSON")
    parser.add_argument("--output", help="Path to write output JSON")
    args = parser.parse_args()

    output_path = Path(args.output) if args.output else None

    try:
        result = run_review(_read_json(Path(args.input)))
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
