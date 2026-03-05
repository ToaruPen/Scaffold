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

_VALID_RESOLUTION_STATUSES = {"addressed", "deferred", "rejected"}
_FALLBACK_RESOLUTION_STATUS = "deferred"


def _require_iterations(bot_feedback: dict[str, Any]) -> list[dict[str, Any]]:
    raw = bot_feedback.get("iterations")
    if not isinstance(raw, list) or not raw:
        raise ValueError("missing or invalid non-empty list: bot_feedback.iterations")

    values: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("invalid object element: bot_feedback.iterations")
        values.append(item)
    return values


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = require_text(payload, "request_id")
    scope_id = require_text(payload, "scope_id")
    run_id = require_text(payload, "run_id")
    artifact_path = require_text(payload, "artifact_path")

    bot_feedback = require_object(payload, "bot_feedback")
    pr_url = require_text(bot_feedback, "pr_url", "bot_feedback")
    iterations = _require_iterations(bot_feedback)

    mismatch_reasons: list[str] = []
    normalized_iterations: list[dict[str, str]] = []
    for index, iteration in enumerate(iterations):
        parent = f"bot_feedback.iterations[{index}]"
        bot_name = require_text(iteration, "bot_name", parent)
        feedback_ref = require_text(iteration, "feedback_ref", parent)
        resolution_status = require_text(iteration, "resolution_status", parent).lower()
        resolution_ref = require_text(iteration, "resolution_ref", parent)
        normalized_resolution_status = resolution_status

        if resolution_status not in _VALID_RESOLUTION_STATUSES:
            mismatch_reasons.append("invalid_resolution_status")
            normalized_resolution_status = _FALLBACK_RESOLUTION_STATUS

        normalized_iterations.append(
            {
                "bot_name": bot_name,
                "feedback_ref": feedback_ref,
                "resolution_status": normalized_resolution_status,
                "resolution_ref": resolution_ref,
            }
        )

    mismatch_reasons = list(dict.fromkeys(mismatch_reasons))
    passed = len(mismatch_reasons) == 0
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "pr_url": pr_url,
        "iterations": normalized_iterations,
        "iteration_count": len(normalized_iterations),
        "mismatch_reasons": mismatch_reasons,
    }
    if not passed:
        result["errors"] = [
            error_dict("E_PROVIDER_FAILURE", "pr bot iteration check failed", "bot")
        ]
    return result, passed


def main() -> int:
    args = parse_gate_args("Validate pr-bot-iteration contract")
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
            "pr_url": "unknown",
            "iterations": [
                {
                    "bot_name": "unknown",
                    "feedback_ref": "unknown",
                    "resolution_status": "deferred",
                    "resolution_ref": "unknown",
                }
            ],
            "iteration_count": 1,
            "mismatch_reasons": ["invalid_input"],
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "bot")],
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
