from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

REVIEW_STUB = Path("framework/scripts/lib/review_engine_stub.py")
VCS_STUB = Path("framework/scripts/lib/vcs_stub.py")
BOT_STUB = Path("framework/scripts/lib/bot_stub.py")


def _run_script(script: Path, payload: Mapping[str, object]) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        input_path = Path(tmp) / "input.json"
        output_path = Path(tmp) / "output.json"
        input_path.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(script),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )


class AdapterStubTests(unittest.TestCase):
    def test_review_engine_stub_returns_schema_shaped_result(self) -> None:
        payload = {
            "request_id": "req-a-1",
            "scope_id": "issue-9",
            "run_id": "run-1",
            "diff_mode": "range",
            "head_sha": "abcdef1",
            "base_sha": "1234567",
            "review_goal": "contract smoke",
            "schema_version": "1",
        }

        result = _run_script(REVIEW_STUB, payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "approved")
        self.assertIn("evidence", body)
        self.assertEqual(body["evidence"]["head_sha"], "abcdef1")

    def test_vcs_stub_resolve_scope_reports_mismatch(self) -> None:
        payload = {
            "operation": "resolve_scope",
            "request_id": "req-a-2",
            "scope_id": "issue-9",
            "run_id": "run-1",
            "current_branch": "feat/issue-10",
            "expected_branch": "feat/issue-9",
            "head_sha": "abcdef1",
            "artifact_path": "artifacts/reviews/issue-9/run-1/scope-lock.json",
        }

        result = _run_script(VCS_STUB, payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertFalse(body["matched"])
        self.assertIn("branch_mismatch", body["mismatch_reasons"])

    def test_bot_stub_fetch_feedback_returns_no_findings_batch(self) -> None:
        payload = {
            "operation": "fetch_feedback",
            "pr_number": 42,
            "cycle": 1,
        }

        result = _run_script(BOT_STUB, payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "no_findings")
        self.assertEqual(body["findings"], [])

    def test_stub_returns_invalid_input_for_unknown_operation(self) -> None:
        payload = {
            "operation": "unknown",
        }

        result = _run_script(VCS_STUB, payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "invalid_input")
        self.assertEqual(body["errors"][0]["code"], "E_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
