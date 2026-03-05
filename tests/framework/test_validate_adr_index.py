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


def _write_adr(
    path: Path,
    *,
    adr_id: str,
    title: str,
    status: str,
    supersedes: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
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
        "## Date",
        "- 2026-03-05",
        "",
        "## Decision",
        "Use a deterministic validator output.",
        "",
    ]
    if supersedes:
        lines.extend(["## Supersedes (Optional)", *[f"- {item}" for item in supersedes], ""])
    lines.extend(["## References", "- Issue: https://example.com/issues/1", ""])
    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def _write_decisions_index(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Decisions Index",
        "",
        "Generated from ADR files. Do not edit manually.",
        "",
        "## Decision Index",
        "",
        "| ADR ID | Title | Decision Summary | Issue | ADR Path |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row["adr_id"],
                    row["title"],
                    row["decision_summary"],
                    row["issue_url"],
                    row["file_path"],
                ]
            )
            + " |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


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
            _write_decisions_index(
                repo_root / "docs/decisions.md",
                [
                    {
                        "adr_id": "ADR-001",
                        "title": "First",
                        "decision_summary": "Use a deterministic validator output.",
                        "issue_url": "https://example.com/issues/1",
                        "file_path": "docs/adr/ADR-001.md",
                    },
                    {
                        "adr_id": "ADR-002",
                        "title": "Second",
                        "decision_summary": "Use a deterministic validator output.",
                        "issue_url": "https://example.com/issues/1",
                        "file_path": "docs/adr/ADR-002.md",
                    },
                ],
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
                            "date": "2026-03-05",
                            "file_path": "docs/adr/ADR-001.md",
                            "decision_summary": "Use a deterministic validator output.",
                            "issue_url": "https://example.com/issues/1",
                        },
                        {
                            "adr_id": "ADR-002",
                            "title": "Second",
                            "status": "proposed",
                            "date": "2026-03-05",
                            "file_path": "docs/adr/ADR-002.md",
                            "decision_summary": "Use a deterministic validator output.",
                            "issue_url": "https://example.com/issues/1",
                        },
                    ]
                },
            }
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 0)
            body = json.loads(result.stdout)
            self.assertEqual(body["status"], "pass")

    def test_passes_when_body_adr_id_is_lowercase(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp:
            repo_root = Path(repo_tmp)
            _write_adr(
                repo_root / "docs/adr/ADR-040.md",
                adr_id="adr-040",
                title="Lowercase ID",
                status="accepted",
            )
            _write_decisions_index(
                repo_root / "docs/decisions.md",
                [
                    {
                        "adr_id": "ADR-040",
                        "title": "Lowercase ID",
                        "decision_summary": "Use a deterministic validator output.",
                        "issue_url": "https://example.com/issues/1",
                        "file_path": "docs/adr/ADR-040.md",
                    }
                ],
            )

            payload = {
                "request_id": "req-adr-11",
                "scope_id": "issue-14",
                "run_id": "run-11",
                "artifact_path": "docs/adr/index.json",
                "adr_index": {
                    "entries": [
                        {
                            "adr_id": "ADR-040",
                            "title": "Lowercase ID",
                            "status": "accepted",
                            "date": "2026-03-05",
                            "file_path": "docs/adr/ADR-040.md",
                            "decision_summary": "Use a deterministic validator output.",
                            "issue_url": "https://example.com/issues/1",
                        }
                    ]
                },
            }
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 0)
            body = json.loads(result.stdout)
            self.assertEqual(body["status"], "pass")

    def test_passes_when_body_uses_decision_summary_section(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp:
            repo_root = Path(repo_tmp)
            adr_path = repo_root / "docs/adr/ADR-042.md"
            adr_path.parent.mkdir(parents=True, exist_ok=True)
            adr_path.write_text(
                "\n".join(
                    [
                        "# ADR",
                        "",
                        "## ADR ID",
                        "- ADR-042",
                        "",
                        "## Title",
                        "Decision Summary Section",
                        "",
                        "## Status",
                        "- accepted",
                        "",
                        "## Date",
                        "- 2026-03-05",
                        "",
                        "## Decision Summary",
                        "Use Decision Summary heading.",
                        "",
                        "## References",
                        "- Issue: https://example.com/issues/1",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            _write_decisions_index(
                repo_root / "docs/decisions.md",
                [
                    {
                        "adr_id": "ADR-042",
                        "title": "Decision Summary Section",
                        "decision_summary": "Use Decision Summary heading.",
                        "issue_url": "https://example.com/issues/1",
                        "file_path": "docs/adr/ADR-042.md",
                    }
                ],
            )

            payload = {
                "request_id": "req-adr-13",
                "scope_id": "issue-14",
                "run_id": "run-13",
                "artifact_path": "docs/adr/index.json",
                "adr_index": {
                    "entries": [
                        {
                            "adr_id": "ADR-042",
                            "title": "Decision Summary Section",
                            "status": "accepted",
                            "date": "2026-03-05",
                            "file_path": "docs/adr/ADR-042.md",
                            "decision_summary": "Use Decision Summary heading.",
                            "issue_url": "https://example.com/issues/1",
                        }
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
                            "date": "2026-03-05",
                            "file_path": "docs/adr/ADR-001.md",
                            "decision_summary": "Use a deterministic validator output.",
                            "issue_url": "https://example.com/issues/1",
                        },
                        {
                            "adr_id": "ADR-001",
                            "title": "Duplicate",
                            "status": "accepted",
                            "date": "2026-03-05",
                            "file_path": "docs/adr/ADR-001-copy.md",
                            "decision_summary": "Use a deterministic validator output.",
                            "issue_url": "https://example.com/issues/1",
                        },
                    ]
                },
            }
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 2)
            body = json.loads(result.stdout)
            self.assertIn("duplicate_adr_id", body["mismatch_reasons"])

    def test_fails_when_decisions_index_mismatches_index(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp:
            repo_root = Path(repo_tmp)
            _write_adr(
                repo_root / "docs/adr/ADR-020.md",
                adr_id="ADR-020",
                title="Consistent Title",
                status="accepted",
            )
            _write_decisions_index(
                repo_root / "docs/decisions.md",
                [
                    {
                        "adr_id": "ADR-020",
                        "title": "Different Title",
                        "decision_summary": "Use a deterministic validator output.",
                        "issue_url": "https://example.com/issues/1",
                        "file_path": "docs/adr/ADR-020.md",
                    }
                ],
            )
            payload = {
                "request_id": "req-adr-9",
                "scope_id": "issue-14",
                "run_id": "run-9",
                "artifact_path": "docs/adr/index.json",
                "adr_index": {
                    "entries": [
                        {
                            "adr_id": "ADR-020",
                            "title": "Consistent Title",
                            "status": "accepted",
                            "date": "2026-03-05",
                            "file_path": "docs/adr/ADR-020.md",
                            "decision_summary": "Use a deterministic validator output.",
                            "issue_url": "https://example.com/issues/1",
                        }
                    ]
                },
            }
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 2)
            body = json.loads(result.stdout)
            self.assertIn("decisions_index_mismatch", body["mismatch_reasons"])

    def test_fails_when_decisions_index_has_duplicate_adr_rows(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp:
            repo_root = Path(repo_tmp)
            _write_adr(
                repo_root / "docs/adr/ADR-030.md",
                adr_id="ADR-030",
                title="Duplicate Row Check",
                status="accepted",
            )
            _write_decisions_index(
                repo_root / "docs/decisions.md",
                [
                    {
                        "adr_id": "ADR-030",
                        "title": "Duplicate Row Check",
                        "decision_summary": "Use a deterministic validator output.",
                        "issue_url": "https://example.com/issues/1",
                        "file_path": "docs/adr/ADR-030.md",
                    },
                    {
                        "adr_id": "ADR-030",
                        "title": "Duplicate Row Check",
                        "decision_summary": "Use a deterministic validator output.",
                        "issue_url": "https://example.com/issues/1",
                        "file_path": "docs/adr/ADR-030.md",
                    },
                ],
            )

            payload = {
                "request_id": "req-adr-10",
                "scope_id": "issue-14",
                "run_id": "run-10",
                "artifact_path": "docs/adr/index.json",
                "adr_index": {
                    "entries": [
                        {
                            "adr_id": "ADR-030",
                            "title": "Duplicate Row Check",
                            "status": "accepted",
                            "date": "2026-03-05",
                            "file_path": "docs/adr/ADR-030.md",
                            "decision_summary": "Use a deterministic validator output.",
                            "issue_url": "https://example.com/issues/1",
                        }
                    ]
                },
            }
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 2)
            body = json.loads(result.stdout)
            self.assertIn("decisions_index_duplicate_adr_id", body["mismatch_reasons"])

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
                            "date": "2026-03-05",
                            "file_path": "docs/adr/ADR-404.md",
                            "decision_summary": "Use a deterministic validator output.",
                            "issue_url": "https://example.com/issues/1",
                        }
                    ]
                },
            }
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 2)
            body = json.loads(result.stdout)
            self.assertIn("missing_adr_file", body["mismatch_reasons"])

    def test_fails_when_adr_file_path_is_absolute_outside_repo(self) -> None:
        with (
            tempfile.TemporaryDirectory() as repo_tmp,
            tempfile.TemporaryDirectory() as outside_tmp,
        ):
            repo_root = Path(repo_tmp)
            outside_adr = Path(outside_tmp) / "ADR-900.md"
            _write_adr(outside_adr, adr_id="ADR-900", title="Outside", status="accepted")

            payload = {
                "request_id": "req-adr-7",
                "scope_id": "issue-14",
                "run_id": "run-7",
                "artifact_path": "docs/adr/index.json",
                "adr_index": {
                    "entries": [
                        {
                            "adr_id": "ADR-900",
                            "title": "Outside",
                            "status": "accepted",
                            "date": "2026-03-05",
                            "file_path": str(outside_adr),
                            "decision_summary": "Use a deterministic validator output.",
                            "issue_url": "https://example.com/issues/1",
                        }
                    ]
                },
            }
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 2)
            body = json.loads(result.stdout)
            self.assertIn("adr_file_outside_repo", body["mismatch_reasons"])

    def test_fails_when_adr_file_path_traverses_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp:
            repo_root = Path(repo_tmp)
            outside_adr = (repo_root / ".." / "ADR-901.md").resolve()
            _write_adr(outside_adr, adr_id="ADR-901", title="Traversal", status="accepted")

            payload = {
                "request_id": "req-adr-8",
                "scope_id": "issue-14",
                "run_id": "run-8",
                "artifact_path": "docs/adr/index.json",
                "adr_index": {
                    "entries": [
                        {
                            "adr_id": "ADR-901",
                            "title": "Traversal",
                            "status": "accepted",
                            "date": "2026-03-05",
                            "file_path": "../ADR-901.md",
                            "decision_summary": "Use a deterministic validator output.",
                            "issue_url": "https://example.com/issues/1",
                        }
                    ]
                },
            }
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 2)
            body = json.loads(result.stdout)
            self.assertIn("adr_file_outside_repo", body["mismatch_reasons"])

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
                            "date": "2026-03-05",
                            "file_path": "docs/adr/ADR-010.md",
                            "decision_summary": "Use a deterministic validator output.",
                            "issue_url": "https://example.com/issues/1",
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
                            "date": "2026-03-05",
                            "file_path": "docs/adr/ADR-011.md",
                            "decision_summary": "Use a deterministic validator output.",
                            "issue_url": "https://example.com/issues/1",
                        }
                    ]
                },
            }
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 2)
            body = json.loads(result.stdout)
            self.assertIn("adr_metadata_missing", body["mismatch_reasons"])

    def test_fails_when_supersedes_mismatches_body(self) -> None:
        with tempfile.TemporaryDirectory() as repo_tmp:
            repo_root = Path(repo_tmp)
            _write_adr(
                repo_root / "docs/adr/ADR-041.md",
                adr_id="ADR-041",
                title="Supersedes Mismatch",
                status="accepted",
                supersedes=["ADR-001"],
            )
            _write_decisions_index(
                repo_root / "docs/decisions.md",
                [
                    {
                        "adr_id": "ADR-041",
                        "title": "Supersedes Mismatch",
                        "decision_summary": "Use a deterministic validator output.",
                        "issue_url": "https://example.com/issues/1",
                        "file_path": "docs/adr/ADR-041.md",
                    }
                ],
            )
            payload = {
                "request_id": "req-adr-12",
                "scope_id": "issue-14",
                "run_id": "run-12",
                "artifact_path": "docs/adr/index.json",
                "adr_index": {
                    "entries": [
                        {
                            "adr_id": "ADR-041",
                            "title": "Supersedes Mismatch",
                            "status": "accepted",
                            "date": "2026-03-05",
                            "file_path": "docs/adr/ADR-041.md",
                            "decision_summary": "Use a deterministic validator output.",
                            "issue_url": "https://example.com/issues/1",
                            "supersedes": ["ADR-002"],
                        }
                    ]
                },
            }
            result = self._run(payload, cwd=repo_root)
            self.assertEqual(result.returncode, 2)
            body = json.loads(result.stdout)
            self.assertIn("adr_metadata_mismatch", body["mismatch_reasons"])

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
