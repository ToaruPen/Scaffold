from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

SCRIPT = Path("framework/scripts/gates/validate_issue_targets.py")


class ValidateIssueTargetsTests(unittest.TestCase):
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

    def test_passes_when_issue_targets_match_scope(self) -> None:
        payload = {
            "request_id": "req-i-1",
            "scope_id": "issue-3",
            "run_id": "run-1",
            "artifact_path": "artifacts/issues/issue-3.json",
            "issue": {
                "issue_id": "issue-3",
                "change_targets": ["framework/scripts/gates/", "tests/framework/"],
                "estimated_scope": "medium",
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")

    def test_fails_when_issue_id_mismatches_scope(self) -> None:
        payload = {
            "request_id": "req-i-2",
            "scope_id": "issue-3",
            "run_id": "run-2",
            "artifact_path": "artifacts/issues/issue-3.json",
            "issue": {
                "issue_id": "issue-999",
                "change_targets": ["framework/scripts/gates/"],
                "estimated_scope": "small",
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("issue_scope_mismatch", body["mismatch_reasons"])

    def test_fails_with_invalid_input(self) -> None:
        payload = {
            "request_id": "req-i-3",
            "scope_id": "issue-3",
            "run_id": "run-3",
            "artifact_path": "artifacts/issues/issue-3.json",
            "issue": {
                "issue_id": "issue-3",
                "change_targets": [],
                "estimated_scope": "small",
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertEqual(body["errors"][0]["code"], "E_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
