from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "framework/scripts/ci/sync_adr_index.py"


class SyncAdrIndexTests(unittest.TestCase):
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

            try:
                result = subprocess.run(
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
                    cwd=str(repo_root),
                    timeout=60,
                )
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout if isinstance(exc.stdout, str) else ""
                stderr = exc.stderr if isinstance(exc.stderr, str) else ""
                self.fail(f"sync_adr_index timed out; stdout={stdout!r} stderr={stderr!r}")
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            index_payload = json.loads(
                (repo_root / "docs/adr/index.json").read_text(encoding="utf-8")
            )
            self.assertEqual(index_payload["entries"][0]["adr_id"], "ADR-001")
            self.assertEqual(
                index_payload["entries"][0]["decision_summary"],
                "Keep core commands explicit.",
            )

            decisions_text = (repo_root / "docs/decisions.md").read_text(encoding="utf-8")
            self.assertIn("| ADR-001 |", decisions_text)
            self.assertIn("https://example.com/issues/1", decisions_text)


if __name__ == "__main__":
    unittest.main()
