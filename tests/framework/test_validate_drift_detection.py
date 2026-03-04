from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

SCRIPT = Path("framework/scripts/gates/validate_drift_detection.py")


class ValidateDriftDetectionTests(unittest.TestCase):
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

    def test_passes_when_changes_are_declared(self) -> None:
        payload = {
            "request_id": "req-drift-1",
            "scope_id": "issue-15",
            "run_id": "run-1",
            "artifact_path": "artifacts/drift/issue-15.json",
            "declared_targets": ["src/auth/"],
            "actual_changes": ["src/auth/login.py"],
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")
        self.assertEqual(body["undeclared_additions"], [])

    def test_fails_when_undeclared_change_exists(self) -> None:
        payload = {
            "request_id": "req-drift-2",
            "scope_id": "issue-15",
            "run_id": "run-2",
            "artifact_path": "artifacts/drift/issue-15.json",
            "declared_targets": ["src/auth/"],
            "actual_changes": ["src/auth/login.py", "src/billing/payments.py"],
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("src/billing/payments.py", body["undeclared_additions"])

    def test_unused_declaration_is_warning_only(self) -> None:
        payload = {
            "request_id": "req-drift-3",
            "scope_id": "issue-15",
            "run_id": "run-3",
            "artifact_path": "artifacts/drift/issue-15.json",
            "declared_targets": ["src/auth/", "src/billing/"],
            "actual_changes": ["src/auth/login.py"],
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")
        self.assertIn("src/billing/", body["unused_declarations"])


if __name__ == "__main__":
    unittest.main()
