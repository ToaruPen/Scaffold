from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

SCRIPT = Path("framework/scripts/gates/validate_waiver.py")


class ValidateWaiverTests(unittest.TestCase):
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

    def test_passes_with_valid_waiver(self) -> None:
        payload = {
            "request_id": "req-w-1",
            "scope_id": "issue-16",
            "run_id": "run-1",
            "artifact_path": "artifacts/waivers/issue-16.json",
            "waiver": {
                "gate_id": "drift-detection",
                "reason": "temporary override",
                "approved_by": "repo-owner",
                "approved_at": "2026-03-04T00:00:00Z",
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")

    def test_fails_with_invalid_input(self) -> None:
        payload = {
            "request_id": "req-w-2",
            "scope_id": "issue-16",
            "run_id": "run-2",
            "artifact_path": "artifacts/waivers/issue-16.json",
            "waiver": {
                "gate_id": "drift-detection",
                "approved_by": "repo-owner",
                "approved_at": "2026-03-04T00:00:00Z",
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["errors"][0]["code"], "E_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
