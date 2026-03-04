from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

SCRIPT = Path("framework/scripts/gates/validate_adr_index.py")


class ValidateAdrIndexTests(unittest.TestCase):
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

    def test_passes_with_unique_entries(self) -> None:
        payload = {
            "request_id": "req-adr-1",
            "scope_id": "issue-14",
            "run_id": "run-1",
            "artifact_path": "docs/adr/index.json",
            "adr_index": {
                "entries": [
                    {
                        "adr_id": "ADR-001",
                        "title": "First",
                        "status": "accepted",
                        "file_path": "docs/adr/ADR-001.md",
                    },
                    {
                        "adr_id": "ADR-002",
                        "title": "Second",
                        "status": "proposed",
                        "file_path": "docs/adr/ADR-002.md",
                    },
                ]
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")

    def test_fails_with_duplicate_adr_id(self) -> None:
        payload = {
            "request_id": "req-adr-2",
            "scope_id": "issue-14",
            "run_id": "run-2",
            "artifact_path": "docs/adr/index.json",
            "adr_index": {
                "entries": [
                    {
                        "adr_id": "ADR-001",
                        "title": "First",
                        "status": "accepted",
                        "file_path": "docs/adr/ADR-001.md",
                    },
                    {
                        "adr_id": "ADR-001",
                        "title": "Duplicate",
                        "status": "accepted",
                        "file_path": "docs/adr/ADR-001-copy.md",
                    },
                ]
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertIn("duplicate_adr_id", body["mismatch_reasons"])

    def test_fails_with_invalid_input(self) -> None:
        payload = {
            "request_id": "req-adr-3",
            "scope_id": "issue-14",
            "run_id": "run-3",
            "artifact_path": "docs/adr/index.json",
            "adr_index": {"entries": []},
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["errors"][0]["code"], "E_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
