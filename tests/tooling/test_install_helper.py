"""Tests for the Scaffold install helper CLI."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tooling/install/install_helper.py"


def _load_script_module() -> ModuleType:
    """Load and execute ``install_helper.py`` for test-time access."""
    spec = importlib.util.spec_from_file_location("install_helper_module", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class InstallHelperTests(unittest.TestCase):
    """Test suite for install_helper CLI behavior."""

    script: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.script = _load_script_module()

    def _run_main(self, argv: list[str]) -> tuple[int, str, str]:
        """Run main() with patched argv, return (exit_code, stdout, stderr)."""
        with patch.object(sys, "argv", argv):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                exit_code: int = self.script.main()
        return exit_code, out.getvalue(), err.getvalue()

    @staticmethod
    def _make_clean_repo(path: Path) -> None:
        """Create and configure a clean temporary git repository."""
        subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=path,
            capture_output=True,
            check=True,
        )

    def _argv(self, target: Path, *extra: str) -> list[str]:
        """Build ``sys.argv`` values for install_helper invocations."""
        return [
            "install_helper.py",
            "--target-repo",
            str(target),
            "--scaffold-repo",
            str(REPO_ROOT),
            *extra,
        ]

    def test_preflight_pass_clean_repo(self) -> None:
        """Verify clean repository passes preflight checks."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._make_clean_repo(repo)
            rc, out, err = self._run_main(self._argv(repo))
            self.assertEqual(rc, 0)
            self.assertIn("All preflight checks passed", out)
            self.assertEqual(err, "")

    def test_preflight_fail_not_git(self) -> None:
        """Fail preflight check when target is not a git repository."""
        with tempfile.TemporaryDirectory() as tmp:
            rc, _out, err = self._run_main(self._argv(Path(tmp)))
            self.assertEqual(rc, 2)
            self.assertIn("Preflight checks failed", err)
            self.assertIn("is_git_repo", err)

    def test_preflight_fail_existing_scaffold(self) -> None:
        """Fail preflight check when scaffold directories already exist."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._make_clean_repo(repo)
            (repo / ".scaffold").mkdir()
            rc, _out, err = self._run_main(self._argv(repo))
            self.assertEqual(rc, 2)
            self.assertIn("Preflight checks failed", err)
            self.assertIn("no_existing_scaffold", err)

    def test_preflight_fail_dirty_tree(self) -> None:
        """Fail preflight check when working tree has uncommitted changes."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._make_clean_repo(repo)
            (repo / "dirty.txt").write_text("uncommitted\n", encoding="utf-8")
            rc, _out, err = self._run_main(self._argv(repo))
            self.assertEqual(rc, 2)
            self.assertIn("Preflight checks failed", err)
            self.assertIn("clean_working_tree", err)

    def test_dry_run_shows_plan(self) -> None:
        """Dry run prints installation plan and makes no changes."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._make_clean_repo(repo)
            rc, out, _err = self._run_main(self._argv(repo, "--dry-run"))
            self.assertEqual(rc, 0)
            self.assertIn("Installation plan", out)
            self.assertIn("Dry run complete. No changes made.", out)
            self.assertFalse((repo / ".scaffold").exists())

    def test_no_flag_shows_safe_message(self) -> None:
        """Without --execute, emit the safe-to-run message."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._make_clean_repo(repo)
            rc, out, _err = self._run_main(self._argv(repo))
            self.assertEqual(rc, 0)
            self.assertIn("To proceed, add --execute to run the installation.", out)

    def test_help_output(self) -> None:
        """Requesting help prints usage and exits with code zero."""
        out, err = io.StringIO(), io.StringIO()
        with (
            patch.object(sys, "argv", ["install_helper.py", "--help"]),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
            self.assertRaises(SystemExit) as cm,
        ):
            self.script.main()
        self.assertEqual(cm.exception.code, 0)
        combined = out.getvalue() + err.getvalue()
        self.assertIn("usage:", combined.lower())


if __name__ == "__main__":
    unittest.main()
