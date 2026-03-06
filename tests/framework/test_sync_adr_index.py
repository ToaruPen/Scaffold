from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, cast

from framework.scripts.lib.adr_index_sync import AdrRecord, build_index_payload

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "framework/scripts/ci/sync_adr_index.py"


def _run_sync(
    *,
    repo_root: Path,
    adr_dir: Path,
    index_path: Path,
    decisions_path: Path,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    run_cwd = cwd if cwd is not None else repo_root
    try:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--adr-dir",
                str(adr_dir),
                "--index-path",
                str(index_path),
                "--decisions-path",
                str(decisions_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(run_cwd),
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        raise AssertionError(
            f"sync_adr_index timed out; stdout={stdout!r} stderr={stderr!r}"
        ) from exc


class SyncAdrIndexTests(unittest.TestCase):
    def test_build_index_payload_normalizes_supersedes_to_list(self) -> None:
        payload = build_index_payload(
            [
                AdrRecord(
                    adr_id="ADR-011",
                    title="Use tuple internally",
                    status="accepted",
                    date="2026-03-05",
                    file_path="docs/adr/ADR-011.md",
                    decision_summary="Normalize payload types.",
                    issue_url="https://example.com/issues/11",
                    supersedes=("ADR-001", "ADR-002"),
                )
            ]
        )

        entries = cast(list[dict[str, Any]], payload["entries"])
        entry = entries[0]
        self.assertEqual(entry["supersedes"], ["ADR-001", "ADR-002"])
        self.assertIsInstance(entry["supersedes"], list)

    def test_generates_index_and_decisions_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as repo_tmp:
            repo_root = Path(repo_tmp)
            adr_file = repo_root / "docs/adr/ADR-001-use-core.md"
            adr_file.parent.mkdir(parents=True, exist_ok=True)
            adr_file.write_text(
                "\n".join(
                    [
                        "# ADR",
                        "",
                        "## ADR ID",
                        "- ADR-001",
                        "",
                        "## Title",
                        "Use core workflow",
                        "",
                        "## Status",
                        "- accepted",
                        "",
                        "## Date",
                        "- 2026-03-05",
                        "",
                        "## Context",
                        "Need stable operation",
                        "",
                        "## Decision Summary",
                        "Keep core commands explicit.",
                        "",
                        "## Consequences",
                        "### Positive",
                        "- Predictable flow",
                        "",
                        "### Negative",
                        "- Extra docs maintenance",
                        "",
                        "## References",
                        "- Issue: https://example.com/issues/1",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            adr_dir = repo_root / "docs/adr"
            index_path = repo_root / "docs/adr/index.json"
            decisions_path = repo_root / "docs/decisions.md"

            result = _run_sync(
                repo_root=repo_root,
                adr_dir=adr_dir,
                index_path=index_path,
                decisions_path=decisions_path,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            index_payload = json.loads(
                (repo_root / "docs/adr/index.json").read_text(encoding="utf-8")
            )
            self.assertEqual(index_payload["entries"][0]["adr_id"], "ADR-001")
            self.assertEqual(
                index_payload["entries"][0]["decision_summary"],
                "Keep core commands explicit.",
            )
            expected_file_path = adr_file.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
            self.assertEqual(
                index_payload["entries"][0]["file_path"],
                expected_file_path,
            )
            self.assertEqual(index_payload["entries"][0]["date"], "2026-03-05")

            decisions_text = (repo_root / "docs/decisions.md").read_text(encoding="utf-8")
            self.assertIn("| ADR-001 |", decisions_text)
            self.assertIn("https://example.com/issues/1", decisions_text)

    def test_fails_fast_when_duplicate_adr_id_exists(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as repo_tmp:
            repo_root = Path(repo_tmp)
            adr_dir = repo_root / "docs/adr"
            adr_dir.mkdir(parents=True, exist_ok=True)

            first_adr = adr_dir / "ADR-001-first.md"
            first_adr.write_text(
                "\n".join(
                    [
                        "# ADR",
                        "",
                        "## ADR ID",
                        "- ADR-001",
                        "",
                        "## Title",
                        "First ADR",
                        "",
                        "## Status",
                        "- accepted",
                        "",
                        "## Date",
                        "- 2026-03-05",
                        "",
                        "## Decision Summary",
                        "First decision.",
                        "",
                        "## References",
                        "- Issue: https://example.com/issues/1",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            duplicate_adr = adr_dir / "ADR-001-duplicate.md"
            duplicate_adr.write_text(
                "\n".join(
                    [
                        "# ADR",
                        "",
                        "## ADR ID",
                        "- ADR-001",
                        "",
                        "## Title",
                        "Duplicate ADR",
                        "",
                        "## Status",
                        "- accepted",
                        "",
                        "## Date",
                        "- 2026-03-05",
                        "",
                        "## Decision Summary",
                        "Duplicate decision.",
                        "",
                        "## References",
                        "- Issue: https://example.com/issues/2",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = _run_sync(
                repo_root=repo_root,
                adr_dir=adr_dir,
                index_path=repo_root / "docs/adr/index.json",
                decisions_path=repo_root / "docs/decisions.md",
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("duplicate ADR ID detected: ADR-001", result.stderr)
            self.assertIn("ADR-001-first.md", result.stderr)
            self.assertIn("ADR-001-duplicate.md", result.stderr)

    def test_rejects_non_iso_date_and_non_uri_issue(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as repo_tmp:
            repo_root = Path(repo_tmp)
            adr_file = repo_root / "docs/adr/ADR-010-invalid.md"
            adr_file.parent.mkdir(parents=True, exist_ok=True)
            adr_file.write_text(
                "\n".join(
                    [
                        "# ADR",
                        "",
                        "## ADR ID",
                        "- ADR-010",
                        "",
                        "## Title",
                        "Invalid ADR metadata",
                        "",
                        "## Status",
                        "- accepted",
                        "",
                        "## Date",
                        "- not-a-date",
                        "",
                        "## Decision Summary",
                        "Invalid metadata should fail.",
                        "",
                        "## References",
                        "- Issue: not-a-uri",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = _run_sync(
                repo_root=repo_root,
                adr_dir=repo_root / "docs/adr",
                index_path=repo_root / "docs/adr/index.json",
                decisions_path=repo_root / "docs/decisions.md",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(
                "invalid date format" in result.stderr or "invalid issue URL" in result.stderr
            )

    def test_rejects_compact_iso_date_without_hyphens(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as repo_tmp:
            repo_root = Path(repo_tmp)
            adr_file = repo_root / "docs/adr/ADR-012-invalid-date-shape.md"
            adr_file.parent.mkdir(parents=True, exist_ok=True)
            adr_file.write_text(
                "\n".join(
                    [
                        "# ADR",
                        "",
                        "## ADR ID",
                        "- ADR-012",
                        "",
                        "## Title",
                        "Invalid date shape",
                        "",
                        "## Status",
                        "- accepted",
                        "",
                        "## Date",
                        "- 20260305",
                        "",
                        "## Decision Summary",
                        "Date must be YYYY-MM-DD.",
                        "",
                        "## References",
                        "- Issue: https://example.com/issues/12",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = _run_sync(
                repo_root=repo_root,
                adr_dir=repo_root / "docs/adr",
                index_path=repo_root / "docs/adr/index.json",
                decisions_path=repo_root / "docs/decisions.md",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid date format", result.stderr)

    def test_rejects_invalid_supersedes_token(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as repo_tmp:
            repo_root = Path(repo_tmp)
            adr_file = repo_root / "docs/adr/ADR-011-invalid-supersedes.md"
            adr_file.parent.mkdir(parents=True, exist_ok=True)
            adr_file.write_text(
                "\n".join(
                    [
                        "# ADR",
                        "",
                        "## ADR ID",
                        "- ADR-011",
                        "",
                        "## Title",
                        "Invalid supersedes token",
                        "",
                        "## Status",
                        "- accepted",
                        "",
                        "## Date",
                        "- 2026-03-05",
                        "",
                        "## Decision Summary",
                        "Supersedes must be strict ADR IDs.",
                        "",
                        "## Supersedes (Optional)",
                        "- ADR-12",
                        "",
                        "## References",
                        "- Issue: https://example.com/issues/11",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = _run_sync(
                repo_root=repo_root,
                adr_dir=repo_root / "docs/adr",
                index_path=repo_root / "docs/adr/index.json",
                decisions_path=repo_root / "docs/decisions.md",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid supersedes token", result.stderr)

    def test_fails_fast_when_adr_dir_is_outside_repository_root(self) -> None:
        with (
            tempfile.TemporaryDirectory() as outside_tmp,
            tempfile.TemporaryDirectory(dir=REPO_ROOT) as output_tmp,
        ):
            outside_root = Path(outside_tmp)
            output_root = Path(output_tmp)

            adr_file = outside_root / "docs/adr/ADR-999-external.md"
            adr_file.parent.mkdir(parents=True, exist_ok=True)
            adr_file.write_text(
                "\n".join(
                    [
                        "# ADR",
                        "",
                        "## ADR ID",
                        "- ADR-999",
                        "",
                        "## Title",
                        "External ADR",
                        "",
                        "## Status",
                        "- accepted",
                        "",
                        "## Date",
                        "- 2026-03-05",
                        "",
                        "## Decision Summary",
                        "External file should fail.",
                        "",
                        "## References",
                        "- Issue: https://example.com/issues/999",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            result = _run_sync(
                repo_root=output_root,
                adr_dir=outside_root / "docs/adr",
                index_path=output_root / "docs/adr/index.json",
                decisions_path=output_root / "docs/decisions.md",
                cwd=output_root,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("outside repository root", result.stderr)


if __name__ == "__main__":
    unittest.main()
