from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(".")
REVIEW_STUB = Path("framework/scripts/lib/review_engine_stub.py")
VCS_STUB = Path("framework/scripts/lib/vcs_stub.py")
BOT_STUB = Path("framework/scripts/lib/bot_stub.py")

REVIEW_SCHEMA = Path("framework/.agent/schemas/adapters/review-engine-result.schema.json")
VCS_SCOPE_SCHEMA = Path("framework/.agent/schemas/gates/vcs-scope-lock-result.schema.json")
BOT_SCHEMA = Path("framework/.agent/schemas/adapters/bot-feedback-batch.schema.json")


def _run_stub(script: Path, payload: Mapping[str, object], output_path: Path) -> None:
    input_path = output_path.parent / "input.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"stub failed: {result.stdout}\n{result.stderr}")


def _assert_schema_valid(schema_path: Path, data_path: Path) -> None:
    result = subprocess.run(
        [
            "check-jsonschema",
            "--schemafile",
            str(schema_path),
            str(data_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"schema validation failed:\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def _assert_schema_invalid(schema_path: Path, data_path: Path) -> None:
    result = subprocess.run(
        [
            "check-jsonschema",
            "--schemafile",
            str(schema_path),
            str(data_path),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    if result.returncode == 0:
        raise AssertionError("schema validation unexpectedly succeeded")


class AdapterContractSchemaTests(unittest.TestCase):
    def test_review_engine_stub_matches_review_engine_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "review_engine_output.json"
            payload = {
                "request_id": "req-c-1",
                "scope_id": "issue-10",
                "run_id": "run-1",
                "diff_mode": "range",
                "head_sha": "abcdef1",
                "base_sha": "1234567",
                "review_goal": "schema contract test",
                "schema_version": "1",
            }

            _run_stub(REVIEW_STUB, payload, output_path)
            _assert_schema_valid(REVIEW_SCHEMA, output_path)

    def test_vcs_resolve_scope_stub_matches_scope_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "vcs_scope_output.json"
            payload = {
                "operation": "resolve_scope",
                "request_id": "req-c-2",
                "scope_id": "issue-10",
                "run_id": "run-1",
                "current_branch": "feat/issue-10",
                "expected_branch": "feat/issue-10",
                "head_sha": "abcdef1",
                "base_sha": "1234567",
                "artifact_path": "artifacts/reviews/issue-10/run-1/scope-lock.json",
            }

            _run_stub(VCS_STUB, payload, output_path)
            _assert_schema_valid(VCS_SCOPE_SCHEMA, output_path)

    def test_bot_fetch_feedback_stub_matches_bot_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "bot_feedback_output.json"
            payload = {
                "operation": "fetch_feedback",
                "pr_number": 42,
                "cycle": 1,
            }

            _run_stub(BOT_STUB, payload, output_path)
            _assert_schema_valid(BOT_SCHEMA, output_path)

    def test_bot_schema_accepts_required_range_and_snippet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "bot_feedback_contract_output.json"
            payload = {
                "provider": "stub-bot",
                "pr_number": 42,
                "cycle": 2,
                "status": "findings_present",
                "findings": [
                    {
                        "finding_id": "bot-f-1",
                        "severity": "P1",
                        "title": "range finding",
                        "detail": "range-based location",
                        "path": "framework/scripts/gates/validate_scope_lock.py",
                        "start_line": 10,
                        "end_line": 18,
                        "snippet": (
                            "if expected_branch != current_branch:\n"
                            '    mismatch_reasons.append("branch_mismatch")'
                        ),
                        "fingerprint": "fp-1",
                    }
                ],
            }

            output_path.write_text(json.dumps(payload), encoding="utf-8")
            _assert_schema_valid(BOT_SCHEMA, output_path)

    def test_review_engine_schema_accepts_required_range_and_snippet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "review_engine_contract_output.json"
            payload = {
                "request_id": "req-c-3",
                "scope_id": "issue-10",
                "run_id": "run-2",
                "status": "needs_changes",
                "summary": "line range included",
                "findings": [
                    {
                        "finding_id": "rev-f-1",
                        "severity": "P2",
                        "title": "range finding",
                        "detail": "range-based location",
                        "path": "framework/scripts/gates/validate_pr_preconditions.py",
                        "start_line": 90,
                        "end_line": 102,
                        "snippet": (
                            "if not scope_lock_matched:\n"
                            '    mismatch_reasons.append("scope_lock_not_matched")'
                        ),
                    }
                ],
                "evidence": {
                    "head_sha": "abcdef1",
                    "artifact_path": "artifacts/reviews/issue-10/run-2/review.json",
                    "created_at": "2026-03-04T00:00:00Z",
                },
                "provider_metadata": {
                    "provider": "stub-review-engine",
                    "model": "deterministic-stub",
                    "duration_ms": 0,
                },
            }

            output_path.write_text(json.dumps(payload), encoding="utf-8")
            _assert_schema_valid(REVIEW_SCHEMA, output_path)

    def test_bot_schema_rejects_legacy_line_only_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "bot_feedback_legacy_line_only.json"
            payload = {
                "provider": "stub-bot",
                "pr_number": 42,
                "cycle": 2,
                "status": "findings_present",
                "findings": [
                    {
                        "finding_id": "bot-f-legacy",
                        "severity": "P2",
                        "title": "legacy line-only finding",
                        "detail": "line only should be rejected",
                        "path": "framework/scripts/gates/validate_scope_lock.py",
                        "line": 10,
                        "fingerprint": "fp-legacy",
                    }
                ],
            }

            output_path.write_text(json.dumps(payload), encoding="utf-8")
            _assert_schema_invalid(BOT_SCHEMA, output_path)

    def test_review_engine_schema_rejects_legacy_line_only_finding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "review_engine_legacy_line_only.json"
            payload = {
                "request_id": "req-c-legacy",
                "scope_id": "issue-10",
                "run_id": "run-legacy",
                "status": "needs_changes",
                "summary": "legacy line-only finding",
                "findings": [
                    {
                        "finding_id": "rev-f-legacy",
                        "severity": "P1",
                        "title": "legacy line-only finding",
                        "detail": "line only should be rejected",
                        "path": "framework/scripts/gates/validate_pr_preconditions.py",
                        "line": 90,
                    }
                ],
                "evidence": {
                    "head_sha": "abcdef1",
                    "artifact_path": "artifacts/reviews/issue-10/run-legacy/review.json",
                    "created_at": "2026-03-04T00:00:00Z",
                },
                "provider_metadata": {
                    "provider": "stub-review-engine",
                },
            }

            output_path.write_text(json.dumps(payload), encoding="utf-8")
            _assert_schema_invalid(REVIEW_SCHEMA, output_path)


if __name__ == "__main__":
    unittest.main()
