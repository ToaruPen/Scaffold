from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "framework/scripts/gates/validate_pr_preconditions.py"


class ValidatePrPreconditionsTests(unittest.TestCase):
    def _run(self, payload: Mapping[str, object]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.json"
            output_path = Path(tmp) / "output.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

    def test_passes_when_scope_and_review_evidence_are_consistent(self) -> None:
        payload = {
            "request_id": "req-pr-1",
            "scope_id": "issue-8",
            "run_id": "run-1",
            "artifact_path": "artifacts/reviews/issue-8/run-1/pr-preconditions.json",
            "expected": {"head_sha": "abcdef1", "base_sha": "1234567"},
            "scope_lock": {"matched": True, "head_sha": "abcdef1", "base_sha": "1234567"},
            "review_evidence": {
                "review_cycle": {
                    "status": "pass",
                    "head_sha": "abcdef1",
                    "base_sha": "1234567",
                    "artifact_path": "artifacts/reviews/issue-8/run-1/review-cycle.json",
                },
                "final_review": {
                    "status": "pass",
                    "head_sha": "abcdef1",
                    "base_sha": "1234567",
                    "artifact_path": "artifacts/reviews/issue-8/run-1/final-review.json",
                },
                "drift_detection": {
                    "status": "pass",
                    "artifact_path": "artifacts/reviews/issue-8/run-1/drift-detection.result.json",
                },
                "adr_index": {
                    "status": "pass",
                    "artifact_path": "artifacts/reviews/issue-8/run-1/adr-index.result.json",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")
        self.assertEqual(body["mismatch_reasons"], [])

    def test_blocks_when_scope_lock_is_not_matched(self) -> None:
        payload = {
            "request_id": "req-pr-2",
            "scope_id": "issue-8",
            "run_id": "run-2",
            "artifact_path": "artifacts/reviews/issue-8/run-2/pr-preconditions.json",
            "expected": {"head_sha": "abcdef1"},
            "scope_lock": {"matched": False, "head_sha": "abcdef1"},
            "review_evidence": {
                "review_cycle": {
                    "status": "pass",
                    "head_sha": "abcdef1",
                    "artifact_path": "y",
                },
                "final_review": {
                    "status": "pass",
                    "head_sha": "abcdef1",
                    "artifact_path": "z",
                },
                "drift_detection": {"status": "pass", "artifact_path": "drift"},
                "adr_index": {"status": "pass", "artifact_path": "adr"},
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("scope_lock_not_matched", body["mismatch_reasons"])

    def test_blocks_on_scope_lock_base_mismatch_and_preserves_scope_lock_value(self) -> None:
        payload = {
            "request_id": "req-pr-2b",
            "scope_id": "issue-8",
            "run_id": "run-2b",
            "artifact_path": "artifacts/reviews/issue-8/run-2b/pr-preconditions.json",
            "expected": {"head_sha": "abcdef1", "base_sha": "1234567"},
            "scope_lock": {"matched": True, "head_sha": "abcdef1", "base_sha": "9999999"},
            "review_evidence": {
                "review_cycle": {
                    "status": "pass",
                    "head_sha": "abcdef1",
                    "base_sha": "1234567",
                    "artifact_path": "y",
                },
                "final_review": {
                    "status": "pass",
                    "head_sha": "abcdef1",
                    "base_sha": "1234567",
                    "artifact_path": "z",
                },
                "drift_detection": {"status": "pass", "artifact_path": "drift"},
                "adr_index": {"status": "pass", "artifact_path": "adr"},
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("scope_lock_base_sha_mismatch", body["mismatch_reasons"])
        self.assertEqual(body["scope_lock"]["base_sha"], "9999999")

    def test_blocks_when_any_review_stage_is_missing(self) -> None:
        payload = {
            "request_id": "req-pr-3",
            "scope_id": "issue-8",
            "run_id": "run-3",
            "artifact_path": "artifacts/reviews/issue-8/run-3/pr-preconditions.json",
            "expected": {"head_sha": "abcdef1"},
            "scope_lock": {"matched": True, "head_sha": "abcdef1"},
            "review_evidence": {
                "review_cycle": {
                    "status": "pass",
                    "head_sha": "abcdef1",
                    "artifact_path": "y",
                },
                "drift_detection": {
                    "status": "pass",
                    "artifact_path": "drift",
                },
                "adr_index": {
                    "status": "pass",
                    "artifact_path": "adr",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("final_review_missing", body["mismatch_reasons"])

    def test_blocks_when_drift_or_adr_gate_is_missing_or_failed(self) -> None:
        payload = {
            "request_id": "req-pr-3b",
            "scope_id": "issue-8",
            "run_id": "run-3b",
            "artifact_path": "artifacts/reviews/issue-8/run-3b/pr-preconditions.json",
            "expected": {"head_sha": "abcdef1"},
            "scope_lock": {"matched": True, "head_sha": "abcdef1"},
            "review_evidence": {
                "review_cycle": {
                    "status": "pass",
                    "head_sha": "abcdef1",
                    "artifact_path": "y",
                },
                "final_review": {
                    "status": "pass",
                    "head_sha": "abcdef1",
                    "artifact_path": "z",
                },
                "drift_detection": {
                    "status": "blocked",
                    "artifact_path": "drift",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("drift_detection_not_passed", body["mismatch_reasons"])
        self.assertIn("adr_index_missing", body["mismatch_reasons"])
        self.assertEqual(body["review_evidence"]["drift_detection"]["status"], "fail")
        self.assertEqual(body["review_evidence"]["adr_index"]["status"], "fail")

    def test_returns_invalid_input_when_expected_missing(self) -> None:
        payload = {
            "request_id": "req-pr-4",
            "scope_id": "issue-8",
            "run_id": "run-4",
            "artifact_path": "artifacts/reviews/issue-8/run-4/pr-preconditions.json",
            "scope_lock": {"matched": True, "head_sha": "abcdef1"},
            "review_evidence": {},
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("invalid_input", body["mismatch_reasons"])
        self.assertEqual(body["errors"][0]["code"], "E_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
