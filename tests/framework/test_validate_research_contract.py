from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

SCRIPT = Path("framework/scripts/gates/validate_research_contract.py")


class ValidateResearchContractTests(unittest.TestCase):
    def _run(self, payload: Mapping[str, object]) -> subprocess.CompletedProcess[str]:
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
            self.assertEqual(output_path.read_text(encoding="utf-8"), result.stdout)
            return result

    def test_passes_with_valid_research_payload(self) -> None:
        payload = {
            "request_id": "req-r-1",
            "scope_id": "issue-1",
            "run_id": "run-1",
            "artifact_path": "artifacts/research/issue-1.json",
            "research": {
                "artifact_ref": "docs/research/2026-03-04-note.md",
                "created_at": "2026-03-04T00:00:00Z",
                "topics": ["architecture", "tradeoff"],
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")
        self.assertEqual(body["mismatch_reasons"], [])

    def test_fails_with_invalid_input(self) -> None:
        payload = {
            "request_id": "req-r-2",
            "scope_id": "issue-1",
            "run_id": "run-2",
            "artifact_path": "artifacts/research/issue-1.json",
            "research": {
                "artifact_ref": "docs/research/2026-03-04-note.md",
                "created_at": "2026-03-04T00:00:00Z",
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
