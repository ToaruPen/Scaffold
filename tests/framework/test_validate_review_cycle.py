from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

SCRIPT = Path("framework/scripts/gates/validate_review_cycle.py")


class ValidateReviewCycleTests(unittest.TestCase):
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

    def test_passes_when_review_cycle_is_approved(self) -> None:
        payload = {
            "request_id": "req-rc-1",
            "scope_id": "issue-7",
            "run_id": "run-1",
            "artifact_path": "artifacts/reviews/issue-7/run-1/review-cycle.json",
            "expected": {"head_sha": "abcdef1", "base_sha": "1234567"},
            "review": {
                "status": "approved",
                "summary": "review cycle passed",
                "evidence": {
                    "head_sha": "abcdef1",
                    "base_sha": "1234567",
                    "artifact_path": "artifacts/reviews/issue-7/run-1/review-cycle.json",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")

    def test_blocks_when_review_status_needs_changes(self) -> None:
        payload = {
            "request_id": "req-rc-2",
            "scope_id": "issue-7",
            "run_id": "run-2",
            "artifact_path": "artifacts/reviews/issue-7/run-2/review-cycle.json",
            "expected": {"head_sha": "abcdef1"},
            "review": {
                "status": "needs_changes",
                "summary": "critical finding remains",
                "evidence": {
                    "head_sha": "abcdef1",
                    "artifact_path": "artifacts/reviews/issue-7/run-2/review-cycle.json",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("review_not_approved", body["mismatch_reasons"])

    def test_returns_invalid_input_when_expected_missing(self) -> None:
        payload = {
            "request_id": "req-rc-3",
            "scope_id": "issue-7",
            "run_id": "run-3",
            "artifact_path": "artifacts/reviews/issue-7/run-3/review-cycle.json",
            "review": {
                "status": "approved",
                "summary": "ok",
                "evidence": {
                    "head_sha": "abcdef1",
                    "artifact_path": "artifacts/reviews/issue-7/run-3/review-cycle.json",
                },
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("invalid_input", body["mismatch_reasons"])
        self.assertEqual(body["errors"][0]["code"], "E_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
