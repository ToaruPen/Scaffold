from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCRIPT = Path("framework/scripts/gates/validate_overlap_safety.py")


class ValidateOverlapSafetyTests(unittest.TestCase):
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

    def test_passes_when_no_overlap_with_active_scopes(self) -> None:
        payload = {
            "request_id": "req-1",
            "scope_id": "issue-5",
            "run_id": "run-1",
            "artifact_path": "artifacts/reviews/issue-5/run-1/overlap-safety.json",
            "current_targets": [
                "framework/scripts/gates/validate_scope_lock.py",
                "framework/scripts/gates/validate_overlap_safety.py",
            ],
            "active_scopes": [
                {
                    "scope_id": "issue-4",
                    "status": "active",
                    "targets": ["framework/scripts/gates/validate_review_cycle.py"],
                }
            ],
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")
        self.assertEqual(body["overlaps"], [])

    def test_fails_when_overlap_detected_without_waiver(self) -> None:
        payload = {
            "request_id": "req-2",
            "scope_id": "issue-5",
            "run_id": "run-2",
            "artifact_path": "artifacts/reviews/issue-5/run-2/overlap-safety.json",
            "current_targets": ["framework/scripts/gates/validate_scope_lock.py"],
            "active_scopes": [
                {
                    "scope_id": "issue-4",
                    "status": "active",
                    "targets": [
                        "framework/scripts/gates/validate_scope_lock.py",
                        "framework/scripts/gates/validate_review_cycle.py",
                    ],
                }
            ],
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertEqual(body["overlaps"][0]["scope_id"], "issue-4")
        self.assertIn(
            "framework/scripts/gates/validate_scope_lock.py",
            body["overlaps"][0]["paths"],
        )

    def test_passes_when_overlap_is_waived(self) -> None:
        payload = {
            "request_id": "req-3",
            "scope_id": "issue-5",
            "run_id": "run-3",
            "artifact_path": "artifacts/reviews/issue-5/run-3/overlap-safety.json",
            "current_targets": ["framework/scripts/gates/validate_scope_lock.py"],
            "allow_overlap_with": ["issue-4"],
            "active_scopes": [
                {
                    "scope_id": "issue-4",
                    "status": "active",
                    "targets": ["framework/scripts/gates/validate_scope_lock.py"],
                }
            ],
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")
        self.assertEqual(body["overlaps"], [])

    def test_returns_invalid_input_for_missing_targets(self) -> None:
        payload = {
            "request_id": "req-4",
            "scope_id": "issue-5",
            "run_id": "run-4",
            "artifact_path": "artifacts/reviews/issue-5/run-4/overlap-safety.json",
            "current_targets": [],
            "active_scopes": [],
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertEqual(body["errors"][0]["code"], "E_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
