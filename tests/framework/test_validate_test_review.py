from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

SCRIPT = Path("framework/scripts/gates/validate_test_review.py")


class ValidateTestReviewTests(unittest.TestCase):
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

    def test_passes_when_review_is_approved_and_sha_matches(self) -> None:
        payload = {
            "request_id": "req-tr-1",
            "scope_id": "issue-7",
            "run_id": "run-1",
            "artifact_path": "artifacts/reviews/issue-7/run-1/test-review.json",
            "expected": {"head_sha": "abcdef1", "base_sha": "1234567"},
            "review": {
                "status": "approved_with_nits",
                "summary": "tests are acceptable",
                "evidence": {
                    "head_sha": "abcdef1",
                    "base_sha": "1234567",
                    "artifact_path": "artifacts/reviews/issue-7/run-1/test-review.json",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")

    def test_blocks_when_head_sha_mismatch(self) -> None:
        payload = {
            "request_id": "req-tr-2",
            "scope_id": "issue-7",
            "run_id": "run-2",
            "artifact_path": "artifacts/reviews/issue-7/run-2/test-review.json",
            "expected": {"head_sha": "abcdef1"},
            "review": {
                "status": "approved",
                "summary": "ok",
                "evidence": {
                    "head_sha": "abc9999",
                    "artifact_path": "artifacts/reviews/issue-7/run-2/test-review.json",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("head_sha_mismatch", body["mismatch_reasons"])

    def test_blocks_when_review_status_is_not_approved(self) -> None:
        payload = {
            "request_id": "req-tr-2a",
            "scope_id": "issue-7",
            "run_id": "run-2a",
            "artifact_path": "artifacts/reviews/issue-7/run-2a/test-review.json",
            "expected": {"head_sha": "abcdef1"},
            "review": {
                "status": "needs_changes",
                "summary": "fix tests first",
                "evidence": {
                    "head_sha": "abcdef1",
                    "artifact_path": "artifacts/reviews/issue-7/run-2a/test-review.json",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("review_not_approved", body["mismatch_reasons"])

    def test_blocks_when_artifact_path_is_mismatched(self) -> None:
        payload = {
            "request_id": "req-tr-2c",
            "scope_id": "issue-7",
            "run_id": "run-2c",
            "artifact_path": "artifacts/reviews/issue-7/run-2c/test-review.json",
            "expected": {"head_sha": "abcdef1"},
            "review": {
                "status": "approved",
                "summary": "ok",
                "evidence": {
                    "head_sha": "abcdef1",
                    "artifact_path": "artifacts/reviews/issue-7/run-2c/other.json",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("artifact_path_mismatch", body["mismatch_reasons"])

    def test_blocks_when_expected_base_sha_exists_but_evidence_base_sha_missing(self) -> None:
        payload = {
            "request_id": "req-tr-2b",
            "scope_id": "issue-7",
            "run_id": "run-2b",
            "artifact_path": "artifacts/reviews/issue-7/run-2b/test-review.json",
            "expected": {"head_sha": "abcdef1", "base_sha": "1234567"},
            "review": {
                "status": "approved",
                "summary": "ok",
                "evidence": {
                    "head_sha": "abcdef1",
                    "artifact_path": "artifacts/reviews/issue-7/run-2b/test-review.json",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("base_sha_missing", body["mismatch_reasons"])

    def test_blocks_when_base_sha_is_mismatched(self) -> None:
        payload = {
            "request_id": "req-tr-2d",
            "scope_id": "issue-7",
            "run_id": "run-2d",
            "artifact_path": "artifacts/reviews/issue-7/run-2d/test-review.json",
            "expected": {"head_sha": "abcdef1", "base_sha": "1234567"},
            "review": {
                "status": "approved",
                "summary": "ok",
                "evidence": {
                    "head_sha": "abcdef1",
                    "base_sha": "7654321",
                    "artifact_path": "artifacts/reviews/issue-7/run-2d/test-review.json",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("base_sha_mismatch", body["mismatch_reasons"])

    def test_returns_invalid_input_when_review_block_missing(self) -> None:
        payload = {
            "request_id": "req-tr-3",
            "scope_id": "issue-7",
            "run_id": "run-3",
            "artifact_path": "artifacts/reviews/issue-7/run-3/test-review.json",
            "expected": {"head_sha": "abcdef1"},
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("invalid_input", body["mismatch_reasons"])
        self.assertEqual(body["errors"][0]["code"], "E_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
