#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import UTC, datetime
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


def run_review(request: dict[str, Any]) -> dict[str, Any]:
    request_id = require_text(request, "request_id")
    scope_id = require_text(request, "scope_id")
    run_id = require_text(request, "run_id")
    require_text(request, "diff_mode")
    head_sha = require_text(request, "head_sha")
    base_sha = optional_text(request, "base_sha")
    require_text(request, "review_goal")
    require_text(request, "schema_version")

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
    args = parse_gate_args("Review engine adapter stub")

    output_path = Path(args.output) if args.output else None

    try:
        result = run_review(read_json(Path(args.input)))
        exit_code = 0
    except ValueError as exc:
        result = {
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "stub-review-engine")],
            "status": "invalid_input",
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
