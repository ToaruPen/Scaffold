from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

SCRIPT = Path("framework/scripts/gates/validate_mode_selection.py")


class ValidateModeSelectionTests(unittest.TestCase):
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

    def test_passes_for_impl_mode_with_approved_estimate(self) -> None:
        payload = {
            "request_id": "req-mode-1",
            "scope_id": "issue-6",
            "run_id": "run-1",
            "artifact_path": "artifacts/reviews/issue-6/run-1/mode-selection.json",
            "estimate_approval": {
                "status": "approved",
                "artifact_path": "artifacts/reviews/issue-6/run-1/estimate-approval.json",
            },
            "mode_selection": {
                "mode": "impl",
                "reason": "small and isolated change",
                "issue_id": "issue-6",
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")
        self.assertEqual(body["selected_mode"], "impl")

    def test_blocks_when_estimate_not_approved(self) -> None:
        payload = {
            "request_id": "req-mode-2",
            "scope_id": "issue-6",
            "run_id": "run-2",
            "artifact_path": "artifacts/reviews/issue-6/run-2/mode-selection.json",
            "estimate_approval": {
                "status": "rejected",
                "artifact_path": "artifacts/reviews/issue-6/run-2/estimate-approval.json",
            },
            "mode_selection": {
                "mode": "tdd",
                "reason": "bug fix requires red-green cycle",
                "issue_id": "issue-6",
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("estimate_not_approved", body["mismatch_reasons"])

    def test_blocks_custom_mode_without_contract_reference(self) -> None:
        payload = {
            "request_id": "req-mode-3",
            "scope_id": "issue-6",
            "run_id": "run-3",
            "artifact_path": "artifacts/reviews/issue-6/run-3/mode-selection.json",
            "estimate_approval": {
                "status": "approved",
                "artifact_path": "artifacts/reviews/issue-6/run-3/estimate-approval.json",
            },
            "mode_selection": {
                "mode": "custom",
                "reason": "requires hybrid sequence",
                "issue_id": "issue-6",
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("custom_contract_ref_missing", body["mismatch_reasons"])

    def test_returns_invalid_input_when_mode_selection_missing(self) -> None:
        payload = {
            "request_id": "req-mode-4",
            "scope_id": "issue-6",
            "run_id": "run-4",
            "artifact_path": "artifacts/reviews/issue-6/run-4/mode-selection.json",
            "estimate_approval": {
                "status": "approved",
                "artifact_path": "artifacts/reviews/issue-6/run-4/estimate-approval.json",
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
