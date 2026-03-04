from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

SCRIPT = Path("framework/scripts/gates/validate_final_review.py")


class ValidateFinalReviewTests(unittest.TestCase):
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

    def test_passes_when_final_review_is_approved(self) -> None:
        payload = {
            "request_id": "req-fr-1",
            "scope_id": "issue-7",
            "run_id": "run-1",
            "artifact_path": "artifacts/reviews/issue-7/run-1/final-review.json",
            "expected": {"head_sha": "abcdef1", "base_sha": "1234567"},
            "review": {
                "status": "approved",
                "summary": "final check passed",
                "evidence": {
                    "head_sha": "abcdef1",
                    "base_sha": "1234567",
                    "artifact_path": "artifacts/reviews/issue-7/run-1/final-review.json",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")

    def test_blocks_when_final_review_not_fully_approved(self) -> None:
        payload = {
            "request_id": "req-fr-2",
            "scope_id": "issue-7",
            "run_id": "run-2",
            "artifact_path": "artifacts/reviews/issue-7/run-2/final-review.json",
            "expected": {"head_sha": "abcdef1"},
            "review": {
                "status": "approved_with_nits",
                "summary": "minor nits remaining",
                "evidence": {
                    "head_sha": "abcdef1",
                    "artifact_path": "artifacts/reviews/issue-7/run-2/final-review.json",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("final_review_not_approved", body["mismatch_reasons"])

    def test_returns_invalid_input_when_evidence_missing(self) -> None:
        payload = {
            "request_id": "req-fr-3",
            "scope_id": "issue-7",
            "run_id": "run-3",
            "artifact_path": "artifacts/reviews/issue-7/run-3/final-review.json",
            "expected": {"head_sha": "abcdef1"},
            "review": {"status": "approved", "summary": "ok"},
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("invalid_input", body["mismatch_reasons"])
        self.assertEqual(body["errors"][0]["code"], "E_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
