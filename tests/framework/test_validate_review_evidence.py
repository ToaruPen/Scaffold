from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

SCRIPT = Path("framework/scripts/gates/validate_review_evidence.py")
TARGET_FILE = Path("framework/scripts/gates/validate_scope_lock.py")


def _line_with_snippet(path: Path, snippet: str) -> int:
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines, start=1):
        if snippet in line:
            return index
    raise AssertionError(f"snippet not found in {path}: {snippet}")


class ValidateReviewEvidenceTests(unittest.TestCase):
    def _run(
        self,
        payload: Mapping[str, object],
        policy_yaml: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / "input.json"
            output_path = Path(tmp) / "output.json"
            input_path.write_text(json.dumps(payload), encoding="utf-8")
            command = [
                sys.executable,
                str(SCRIPT),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ]
            if policy_yaml is not None:
                policy_path = Path(tmp) / "policy.yaml"
                policy_path.write_text(policy_yaml, encoding="utf-8")
                command.extend(["--policy", str(policy_path)])
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )

    def _base_payload(self, severity: str = "P1") -> dict[str, object]:
        snippet = 'mismatch_reasons.append("branch_mismatch")'
        line = _line_with_snippet(TARGET_FILE, snippet)
        return {
            "request_id": "req-review-evidence-1",
            "scope_id": "issue-15",
            "run_id": "run-1",
            "artifact_path": "artifacts/reviews/issue-15/run-1/review-evidence-link.json",
            "expected": {
                "head_sha": "abcdef1",
                "base_sha": "1234567",
            },
            "review": {
                "status": "needs_changes",
                "summary": "review output",
                "findings": [
                    {
                        "finding_id": "f-1",
                        "severity": severity,
                        "title": "branch mismatch check",
                        "detail": "scope lock branch mismatch should be detected",
                        "path": str(TARGET_FILE),
                        "start_line": line,
                        "end_line": line,
                        "snippet": snippet,
                    }
                ],
                "evidence": {
                    "head_sha": "abcdef1",
                    "base_sha": "1234567",
                    "artifact_path": "artifacts/reviews/issue-15/run-1/review-cycle.json",
                },
            },
        }

    def test_passes_when_finding_location_and_snippet_are_valid(self) -> None:
        result = self._run(self._base_payload())
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")
        self.assertEqual(body["classification_counts"]["verified"], 1)
        self.assertEqual(body["classification_counts"]["unmapped"], 0)
        self.assertIn("policy", body)
        self.assertIn("policy_path", body)

    def test_fails_as_stale_when_head_sha_is_mismatched(self) -> None:
        payload = self._base_payload()
        review = payload["review"]
        assert isinstance(review, dict)
        evidence = review["evidence"]
        assert isinstance(evidence, dict)
        evidence["head_sha"] = "abc9999"

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("head_sha_mismatch", body["mismatch_reasons"])
        self.assertEqual(body["classification_counts"]["stale"], 1)

    def test_fails_when_finding_schema_is_invalid(self) -> None:
        payload = self._base_payload()
        review = payload["review"]
        assert isinstance(review, dict)
        findings = review["findings"]
        assert isinstance(findings, list)
        finding = findings[0]
        assert isinstance(finding, dict)
        del finding["snippet"]

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("schema_invalid_finding_present", body["mismatch_reasons"])
        self.assertEqual(body["classification_counts"]["schema_invalid"], 1)

    def test_fails_when_high_severity_finding_is_unmapped(self) -> None:
        payload = self._base_payload(severity="P0")
        review = payload["review"]
        assert isinstance(review, dict)
        findings = review["findings"]
        assert isinstance(findings, list)
        finding = findings[0]
        assert isinstance(finding, dict)
        finding["start_line"] = 99999
        finding["end_line"] = 99999

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("unmapped_required_severity_finding_present", body["mismatch_reasons"])
        self.assertEqual(body["classification_counts"]["unmapped"], 1)

    def test_passes_with_warning_when_low_severity_finding_is_unmapped(self) -> None:
        payload = self._base_payload(severity="P3")
        review = payload["review"]
        assert isinstance(review, dict)
        findings = review["findings"]
        assert isinstance(findings, list)
        finding = findings[0]
        assert isinstance(finding, dict)
        finding["start_line"] = 99999
        finding["end_line"] = 99999

        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")
        self.assertEqual(body["classification_counts"]["unmapped"], 1)
        self.assertIn("warnings", body)

    def test_fails_with_custom_policy_when_p3_unmapped_is_blocking(self) -> None:
        payload = self._base_payload(severity="P3")
        review = payload["review"]
        assert isinstance(review, dict)
        findings = review["findings"]
        assert isinstance(findings, list)
        finding = findings[0]
        assert isinstance(finding, dict)
        finding["start_line"] = 99999
        finding["end_line"] = 99999

        policy_yaml = "\n".join(
            [
                "rerun:",
                "  fail_on_classifications:",
                "    - stale",
                "    - schema_invalid",
                "  fail_on_unmapped_severity:",
                "    - P3",
            ]
        )
        result = self._run(payload, policy_yaml=policy_yaml)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("unmapped_required_severity_finding_present", body["mismatch_reasons"])

    def test_allows_finding_id_with_index_pattern(self) -> None:
        payload = self._base_payload()
        review = payload["review"]
        assert isinstance(review, dict)
        findings = review["findings"]
        assert isinstance(findings, list)
        finding = findings[0]
        assert isinstance(finding, dict)
        finding["finding_id"] = "index-0"

        result = self._run(payload)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")
        self.assertEqual(body["classification_counts"]["schema_invalid"], 0)

    def test_empty_policy_lists_do_not_fallback_to_defaults(self) -> None:
        payload = self._base_payload(severity="P0")
        review = payload["review"]
        assert isinstance(review, dict)
        findings = review["findings"]
        assert isinstance(findings, list)
        finding = findings[0]
        assert isinstance(finding, dict)
        finding["start_line"] = 99999
        finding["end_line"] = 99999

        policy_yaml = "\n".join(
            [
                "rerun:",
                "  fail_on_classifications:",
                "  fail_on_unmapped_severity:",
            ]
        )
        result = self._run(payload, policy_yaml=policy_yaml)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "pass")
        self.assertEqual(body["classification_counts"]["unmapped"], 1)
        self.assertIn("warnings", body)
        self.assertNotIn("unmapped_required_severity_finding_present", body["mismatch_reasons"])

    def test_returns_invalid_input_when_expected_is_missing(self) -> None:
        payload = self._base_payload()
        del payload["expected"]

        result = self._run(payload)
        self.assertEqual(result.returncode, 2)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "fail")
        self.assertIn("invalid_input", body["mismatch_reasons"])
        self.assertEqual(body["errors"][0]["code"], "E_INPUT_INVALID")


if __name__ == "__main__":
    unittest.main()
