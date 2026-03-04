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


def _build_result(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    request_id = require_text(payload, "request_id")
    scope_id = require_text(payload, "scope_id")
    run_id = require_text(payload, "run_id")
    artifact_path = require_text(payload, "artifact_path")

    expected = require_object(payload, "expected")
    review = require_object(payload, "review")
    evidence = require_object(review, "evidence", "review")

    expected_head = require_text(expected, "head_sha", "expected")
    expected_base = optional_text(expected, "base_sha", "expected")

    review_status = require_text(review, "status", "review").lower()
    review_summary = require_text(review, "summary", "review")
    evidence_head = require_text(evidence, "head_sha", "review.evidence")
    evidence_base = optional_text(evidence, "base_sha", "review.evidence")
    evidence_artifact = require_text(evidence, "artifact_path", "review.evidence")

    mismatch_reasons: list[str] = []
    if review_status not in {"approved", "approved_with_nits"}:
        mismatch_reasons.append("review_not_approved")
    if expected_head != evidence_head:
        mismatch_reasons.append("head_sha_mismatch")
    if expected_base is not None:
        if evidence_base is None:
            mismatch_reasons.append("base_sha_missing")
        elif expected_base != evidence_base:
            mismatch_reasons.append("base_sha_mismatch")
    if artifact_path != evidence_artifact:
        mismatch_reasons.append("artifact_path_mismatch")

    passed = len(mismatch_reasons) == 0
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "stage": "review-cycle",
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "review_status": review_status,
        "summary": review_summary,
        "head_sha": evidence_head,
        "mismatch_reasons": mismatch_reasons,
    }
    if evidence_base is not None:
        result["base_sha"] = evidence_base
    if not passed:
        result["errors"] = [
            error_dict("E_PROVIDER_FAILURE", "review-cycle evidence check failed", "review_engine")
        ]
    return result, passed


def main() -> int:
    args = parse_gate_args("Validate review-cycle evidence contract")
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
            "stage": "review-cycle",
            "status": "fail",
            "artifact_path": "unknown",
            "review_status": "blocked",
            "summary": "invalid_input",
            "head_sha": "unknown",
            "mismatch_reasons": ["invalid_input"],
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "review_engine")],
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
