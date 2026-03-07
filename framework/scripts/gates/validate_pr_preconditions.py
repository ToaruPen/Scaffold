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
    optional_text,
    parse_gate_args,
    read_json,
    require_object,
    require_text,
    write_result,
)

REQUIRED_REVIEW_STAGE_KEYS = ("review_cycle", "final_review")
REQUIRED_GATE_STAGE_KEYS = ("drift_detection", "adr_index")


def _validate_stage(
    *,
    stage_key: str,
    stage_obj: dict[str, Any],
    expected_head: str,
    expected_base: str | None,
    mismatch_reasons: list[str],
) -> dict[str, str]:
    stage_status = require_text(stage_obj, "status", f"review_evidence.{stage_key}").lower()
    stage_head = require_text(stage_obj, "head_sha", f"review_evidence.{stage_key}")
    stage_base = optional_text(stage_obj, "base_sha", f"review_evidence.{stage_key}")
    stage_artifact = require_text(stage_obj, "artifact_path", f"review_evidence.{stage_key}")

    if stage_status != "pass":
        mismatch_reasons.append(f"{stage_key}_not_passed")
    if stage_head != expected_head:
        mismatch_reasons.append(f"{stage_key}_head_sha_mismatch")
    if expected_base is not None:
        if stage_base is None:
            mismatch_reasons.append(f"{stage_key}_base_sha_missing")
        elif stage_base != expected_base:
            mismatch_reasons.append(f"{stage_key}_base_sha_mismatch")

    result = {
        "status": stage_status,
        "head_sha": stage_head,
        "artifact_path": stage_artifact,
    }
    if stage_base is not None:
        result["base_sha"] = stage_base
    return result


def _validate_gate_stage(
    *,
    stage_key: str,
    stage_obj: dict[str, Any],
    mismatch_reasons: list[str],
) -> dict[str, str]:
    raw_stage_status = require_text(stage_obj, "status", f"review_evidence.{stage_key}").lower()
    stage_status = "pass" if raw_stage_status == "pass" else "fail"
    stage_artifact = require_text(stage_obj, "artifact_path", f"review_evidence.{stage_key}")
    if stage_status != "pass":
        mismatch_reasons.append(f"{stage_key}_not_passed")
    return {
        "status": stage_status,
        "artifact_path": stage_artifact,
    }


def _missing_gate_stage_result() -> dict[str, str]:
    return {
        "status": "fail",
        "artifact_path": "unknown",
    }


def _scope_lock_mismatch_reasons(
    *,
    scope_lock_matched: bool,
    scope_lock_head: str,
    scope_lock_base: str | None,
    expected_head: str,
    expected_base: str | None,
) -> list[str]:
    mismatch_reasons: list[str] = []
    if not scope_lock_matched:
        mismatch_reasons.append("scope_lock_not_matched")
    if scope_lock_head != expected_head:
        mismatch_reasons.append("scope_lock_head_sha_mismatch")
    if expected_base is not None:
        if scope_lock_base is None:
            mismatch_reasons.append("scope_lock_base_sha_missing")
        elif scope_lock_base != expected_base:
            mismatch_reasons.append("scope_lock_base_sha_mismatch")
    return mismatch_reasons


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = require_text(payload, "request_id")
    scope_id = require_text(payload, "scope_id")
    run_id = require_text(payload, "run_id")
    artifact_path = require_text(payload, "artifact_path")

    expected = require_object(payload, "expected")
    expected_head = require_text(expected, "head_sha", "expected")
    expected_base = optional_text(expected, "base_sha", "expected")

    scope_lock = require_object(payload, "scope_lock")
    scope_lock_matched = scope_lock.get("matched")
    if not isinstance(scope_lock_matched, bool):
        raise ValueError("missing or invalid boolean: scope_lock.matched")
    scope_lock_head = require_text(scope_lock, "head_sha", "scope_lock")
    scope_lock_base = optional_text(scope_lock, "base_sha", "scope_lock")

    review_evidence = require_object(payload, "review_evidence")

    mismatch_reasons = _scope_lock_mismatch_reasons(
        scope_lock_matched=scope_lock_matched,
        scope_lock_head=scope_lock_head,
        scope_lock_base=scope_lock_base,
        expected_head=expected_head,
        expected_base=expected_base,
    )

    stage_results: dict[str, dict[str, str]] = {}
    for stage_key in REQUIRED_REVIEW_STAGE_KEYS:
        stage_obj = review_evidence.get(stage_key)
        if not isinstance(stage_obj, dict):
            mismatch_reasons.append(f"{stage_key}_missing")
            continue
        stage_results[stage_key] = _validate_stage(
            stage_key=stage_key,
            stage_obj=stage_obj,
            expected_head=expected_head,
            expected_base=expected_base,
            mismatch_reasons=mismatch_reasons,
        )
    for stage_key in REQUIRED_GATE_STAGE_KEYS:
        stage_obj = review_evidence.get(stage_key)
        if not isinstance(stage_obj, dict):
            mismatch_reasons.append(f"{stage_key}_missing")
            stage_results[stage_key] = _missing_gate_stage_result()
            continue
        stage_results[stage_key] = _validate_gate_stage(
            stage_key=stage_key,
            stage_obj=stage_obj,
            mismatch_reasons=mismatch_reasons,
        )

    passed = len(mismatch_reasons) == 0
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "scope_lock": {
            "matched": scope_lock_matched,
            "head_sha": scope_lock_head,
        },
        "review_evidence": stage_results,
        "head_sha": expected_head,
        "mismatch_reasons": mismatch_reasons,
    }
    if expected_base is not None:
        result["base_sha"] = expected_base
    if scope_lock_base is not None:
        result["scope_lock"]["base_sha"] = scope_lock_base

    if not passed:
        result["errors"] = [
            error_dict("E_PROVIDER_FAILURE", "pr preconditions check failed", "vcs")
        ]
    return result, passed


def main() -> int:
    args = parse_gate_args("Validate PR preconditions contract")
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
            "scope_lock": {
                "matched": False,
                "head_sha": "unknown",
            },
            "review_evidence": {},
            "head_sha": "unknown",
            "mismatch_reasons": ["invalid_input"],
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "vcs")],
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
