from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

SCRIPT = Path("framework/scripts/gates/validate_pr_bot_iteration.py")


class ValidatePrBotIterationTests(unittest.TestCase):
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

    def test_passes_when_all_iterations_have_valid_resolution(self) -> None:
        payload = {
            "request_id": "req-bot-1",
            "scope_id": "issue-13",
            "run_id": "run-1",
            "artifact_path": "artifacts/bot/issue-13.json",
            "bot_feedback": {
                "pr_url": "https://github.com/org/repo/pull/1",
                "iterations": [
                    {
                        "bot_name": "codex",
                        "feedback_ref": "artifacts/bot/cycle-1.json",
                        "resolution_status": "addressed",
                        "resolution_ref": "commits/abc1234",
                    }
                ],
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")

    def test_fails_when_resolution_status_is_invalid(self) -> None:
        payload = {
            "request_id": "req-bot-2",
            "scope_id": "issue-13",
            "run_id": "run-2",
            "artifact_path": "artifacts/bot/issue-13.json",
            "bot_feedback": {
                "pr_url": "https://github.com/org/repo/pull/1",
                "iterations": [
                    {
                        "bot_name": "codex",
                        "feedback_ref": "artifacts/bot/cycle-2.json",
                        "resolution_status": "unknown",
                        "resolution_ref": "commits/def5678",
                    }
                ],
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("invalid_resolution_status", body["mismatch_reasons"])

    def test_fails_with_invalid_input(self) -> None:
        payload = {
            "request_id": "req-bot-3",
            "scope_id": "issue-13",
            "run_id": "run-3",
            "artifact_path": "artifacts/bot/issue-13.json",
            "bot_feedback": {"pr_url": "https://github.com/org/repo/pull/1", "iterations": []},
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["errors"][0]["code"], "E_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
