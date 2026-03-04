from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCRIPT = Path("framework/scripts/gates/validate_scope_lock.py")


class ValidateScopeLockTests(unittest.TestCase):
    def _run(self, payload: Mapping[str, Any]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.json"
            output_path = Path(tmp) / "output.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")

            result = subprocess.run(
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
            return result

    def test_passes_when_expected_and_actual_match(self) -> None:
        payload = {
            "request_id": "req-1",
            "scope_id": "issue-5",
            "run_id": "run-1",
            "artifact_path": "artifacts/reviews/issue-5/run-1/scope-lock.json",
            "expected": {
                "branch": "feat/issue-5",
                "head_sha": "abcdef1",
                "base_sha": "1234567",
            },
            "actual": {
                "branch": "feat/issue-5",
                "head_sha": "abcdef1",
                "base_sha": "1234567",
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertTrue(body["matched"])
        self.assertEqual(body["mismatch_reasons"], [])
        self.assertEqual(body["run_id"], "run-1")

    def test_fails_when_branch_or_head_mismatch(self) -> None:
        payload = {
            "request_id": "req-2",
            "scope_id": "issue-5",
            "run_id": "run-2",
            "artifact_path": "artifacts/reviews/issue-5/run-2/scope-lock.json",
            "expected": {
                "branch": "feat/issue-5",
                "head_sha": "abcdef1",
            },
            "actual": {
                "branch": "feat/issue-6",
                "head_sha": "abc9999",
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertFalse(body["matched"])
        self.assertIn("branch_mismatch", body["mismatch_reasons"])
        self.assertIn("head_sha_mismatch", body["mismatch_reasons"])

    def test_fails_when_expected_base_sha_is_missing_in_actual(self) -> None:
        payload = {
            "request_id": "req-2b",
            "scope_id": "issue-5",
            "run_id": "run-2b",
            "artifact_path": "artifacts/reviews/issue-5/run-2b/scope-lock.json",
            "expected": {
                "branch": "feat/issue-5",
                "head_sha": "abcdef1",
                "base_sha": "1234567",
            },
            "actual": {
                "branch": "feat/issue-5",
                "head_sha": "abcdef1",
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertFalse(body["matched"])
        self.assertIn("base_sha_missing", body["mismatch_reasons"])

    def test_returns_invalid_input_on_missing_required_fields(self) -> None:
        payload = {
            "request_id": "req-3",
            "scope_id": "issue-5",
            "run_id": "run-3",
            "expected": {"branch": "feat/issue-5"},
            "actual": {"branch": "feat/issue-5", "head_sha": "abcdef1"},
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["matched"], False)
        self.assertEqual(body["mismatch_reasons"], ["invalid_input"])
        self.assertEqual(body["errors"][0]["code"], "E_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
