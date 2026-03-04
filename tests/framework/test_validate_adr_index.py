from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "framework/scripts/gates/validate_adr_index.py"


def _write_adr(path: Path, *, adr_id: str, title: str, status: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# ADR",
                "",
                "## ADR ID",
                f"- {adr_id}",
                "",
                "## Title",
                title,
                "",
                "## Status",
                f"- {status}",
                "",
            ]
        ),
        encoding="utf-8",
    )


class ValidateAdrIndexTests(unittest.TestCase):
    def _run(
        self,
        payload: Mapping[str, object],
        *,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
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
                cwd=str(cwd) if cwd is not None else None,
            )

    def test_passes_with_unique_entries(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp:
            repo_root = Path(repo_tmp)
            _write_adr(
                repo_root / "docs/adr/ADR-001.md",
                adr_id="ADR-001",
                title="First",
                status="accepted",
            )
            _write_adr(
                repo_root / "docs/adr/ADR-002.md",
                adr_id="ADR-002",
                title="Second",
                status="proposed",
            )
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
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 0)
            body = json.loads(result.stdout)
            self.assertEqual(body["status"], "pass")

    def test_fails_with_duplicate_adr_id(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp:
            repo_root = Path(repo_tmp)
            _write_adr(
                repo_root / "docs/adr/ADR-001.md",
                adr_id="ADR-001",
                title="First",
                status="accepted",
            )
            _write_adr(
                repo_root / "docs/adr/ADR-001-copy.md",
                adr_id="ADR-001",
                title="Duplicate",
                status="accepted",
            )
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
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 2)
            body = json.loads(result.stdout)
            self.assertIn("duplicate_adr_id", body["mismatch_reasons"])

    def test_fails_when_adr_file_path_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp:
            repo_root = Path(repo_tmp)
            payload = {
                "request_id": "req-adr-4",
                "scope_id": "issue-14",
                "run_id": "run-4",
                "artifact_path": "docs/adr/index.json",
                "adr_index": {
                    "entries": [
                        {
                            "adr_id": "ADR-404",
                            "title": "Missing ADR",
                            "status": "accepted",
                            "file_path": "docs/adr/ADR-404.md",
                        }
                    ]
                },
            }
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 2)
            body = json.loads(result.stdout)
            self.assertIn("missing_adr_file", body["mismatch_reasons"])

    def test_fails_when_adr_metadata_mismatches_index(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp:
            repo_root = Path(repo_tmp)
            _write_adr(
                repo_root / "docs/adr/ADR-010.md",
                adr_id="ADR-010",
                title="Different Title",
                status="accepted",
            )
            payload = {
                "request_id": "req-adr-5",
                "scope_id": "issue-14",
                "run_id": "run-5",
                "artifact_path": "docs/adr/index.json",
                "adr_index": {
                    "entries": [
                        {
                            "adr_id": "ADR-010",
                            "title": "Expected Title",
                            "status": "accepted",
                            "file_path": "docs/adr/ADR-010.md",
                        }
                    ]
                },
            }
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 2)
            body = json.loads(result.stdout)
            self.assertIn("adr_metadata_mismatch", body["mismatch_reasons"])

    def test_fails_when_adr_metadata_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp:
            repo_root = Path(repo_tmp)
            invalid_adr_path = repo_root / "docs/adr/ADR-011.md"
            invalid_adr_path.parent.mkdir(parents=True, exist_ok=True)
            invalid_adr_path.write_text("# ADR\n\nmetadata is missing\n", encoding="utf-8")

            payload = {
                "request_id": "req-adr-6",
                "scope_id": "issue-14",
                "run_id": "run-6",
                "artifact_path": "docs/adr/index.json",
                "adr_index": {
                    "entries": [
                        {
                            "adr_id": "ADR-011",
                            "title": "Missing Metadata",
                            "status": "accepted",
                            "file_path": "docs/adr/ADR-011.md",
                        }
                    ]
                },
            }
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 2)
            body = json.loads(result.stdout)
            self.assertIn("adr_metadata_missing", body["mismatch_reasons"])

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
