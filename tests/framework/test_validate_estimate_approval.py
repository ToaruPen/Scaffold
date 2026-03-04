from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

SCRIPT = Path("framework/scripts/gates/validate_estimate_approval.py")


class ValidateEstimateApprovalTests(unittest.TestCase):
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

    def test_passes_for_approved_estimate(self) -> None:
        payload = {
            "request_id": "req-est-1",
            "scope_id": "issue-6",
            "run_id": "run-1",
            "artifact_path": "artifacts/reviews/issue-6/run-1/estimate-approval.json",
            "estimate": {
                "issue_id": "issue-6",
                "estimate_ref": "docs/estimates/issue-6.md",
                "assumptions": ["small diff", "existing patterns reusable"],
            },
            "approval": {
                "status": "approved",
                "approved_by": "product-owner",
                "approved_at": "2026-03-04T10:00:00Z",
                "decision_id": "dec-001",
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")
        self.assertEqual(body["mismatch_reasons"], [])

    def test_blocks_when_estimate_is_not_approved(self) -> None:
        payload = {
            "request_id": "req-est-2",
            "scope_id": "issue-6",
            "run_id": "run-2",
            "artifact_path": "artifacts/reviews/issue-6/run-2/estimate-approval.json",
            "estimate": {
                "issue_id": "issue-6",
                "estimate_ref": "docs/estimates/issue-6.md",
                "assumptions": ["needs extra tests"],
            },
            "approval": {
                "status": "pending",
                "approved_by": "product-owner",
                "approved_at": "2026-03-04T10:01:00Z",
                "decision_id": "dec-002",
            },
        }

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("estimate_not_approved", body["mismatch_reasons"])

    def test_returns_invalid_input_for_missing_required_block(self) -> None:
        payload = {
            "request_id": "req-est-3",
            "scope_id": "issue-6",
            "run_id": "run-3",
            "artifact_path": "artifacts/reviews/issue-6/run-3/estimate-approval.json",
            "estimate": {
                "issue_id": "issue-6",
                "estimate_ref": "docs/estimates/issue-6.md",
                "assumptions": ["default"],
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
