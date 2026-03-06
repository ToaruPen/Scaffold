from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "framework/scripts/gates/validate_spec_quality.py"
CHECK_JSONSCHEMA = REPO_ROOT / ".venv/bin/check-jsonschema"
SCHEMA = REPO_ROOT / "framework/.agent/schemas/gates/spec-quality-result.schema.json"


class ValidateSpecQualityTests(unittest.TestCase):
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

    def test_passes_when_minimum_quality_is_met(self) -> None:
        payload = {
            "request_id": "req-s-1",
            "scope_id": "issue-2",
            "run_id": "run-1",
            "artifact_path": "artifacts/spec/issue-2.json",
            "spec": {
                "artifact_ref": "docs/prd/prd-v1.md",
                "has_acceptance_criteria": True,
                "has_out_of_scope": True,
                "acceptance_criteria_count": 3,
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")

    def test_fails_when_acceptance_criteria_is_missing(self) -> None:
        payload = {
            "request_id": "req-s-2",
            "scope_id": "issue-2",
            "run_id": "run-2",
            "artifact_path": "artifacts/spec/issue-2.json",
            "spec": {
                "artifact_ref": "docs/prd/prd-v1.md",
                "has_acceptance_criteria": False,
                "has_out_of_scope": True,
                "acceptance_criteria_count": 0,
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("acceptance_criteria_missing", body["mismatch_reasons"])
        self.assertEqual(body["acceptance_criteria_count"], 0)

    def test_fails_when_count_is_non_zero_without_acceptance_criteria(self) -> None:
        payload = {
            "request_id": "req-s-4",
            "scope_id": "issue-2",
            "run_id": "run-4",
            "artifact_path": "artifacts/spec/issue-2.json",
            "spec": {
                "artifact_ref": "docs/prd/prd-v1.md",
                "has_acceptance_criteria": False,
                "has_out_of_scope": True,
                "acceptance_criteria_count": 2,
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertIn("acceptance_criteria_count_invalid", body["mismatch_reasons"])
        self.assertEqual(body["acceptance_criteria_count"], 0)

    def test_fails_when_count_is_negative_with_acceptance_criteria(self) -> None:
        payload = {
            "request_id": "req-s-5",
            "scope_id": "issue-2",
            "run_id": "run-5",
            "artifact_path": "artifacts/spec/issue-2.json",
            "spec": {
                "artifact_ref": "docs/prd/prd-v1.md",
                "has_acceptance_criteria": True,
                "has_out_of_scope": True,
                "acceptance_criteria_count": -3,
            },
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertIn("acceptance_criteria_count_invalid", body["mismatch_reasons"])
        self.assertEqual(body["acceptance_criteria_count"], 1)

    def test_schema_rejects_pass_with_non_empty_mismatch_reasons(self) -> None:
        payload = {
            "request_id": "req-s-schema",
            "scope_id": "issue-2",
            "run_id": "run-schema",
            "status": "pass",
            "artifact_path": "artifacts/spec/issue-2.json",
            "spec_ref": "docs/prd/prd-v1.md",
            "has_acceptance_criteria": True,
            "has_out_of_scope": True,
            "acceptance_criteria_count": 1,
            "mismatch_reasons": ["unexpected_reason"],
        }
        with tempfile.TemporaryDirectory() as tmp:
            payload_path = Path(tmp) / "payload.json"
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            result = subprocess.run(
                [
                    str(CHECK_JSONSCHEMA),
                    "--schemafile",
                    str(SCHEMA),
                    str(payload_path),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=REPO_ROOT,
            )
        self.assertNotEqual(result.returncode, 0)

    def test_fails_with_invalid_input(self) -> None:
        payload = {
            "request_id": "req-s-3",
            "scope_id": "issue-2",
            "run_id": "run-3",
            "artifact_path": "artifacts/spec/issue-2.json",
        }
        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertEqual(body["errors"][0]["code"], "E_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
