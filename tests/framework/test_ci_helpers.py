from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from framework.scripts.lib import ci_helpers


class CiHelpersTests(unittest.TestCase):
    def test_run_command_returns_127_when_executable_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            with patch(
                "framework.scripts.lib.ci_helpers.subprocess.run",
                side_effect=FileNotFoundError("No such file or directory: 'git'"),
            ):
                result = ci_helpers.run_command(["git", "status"], cwd=cwd, timeout_sec=5)

        self.assertEqual(result.returncode, 127)
        self.assertEqual(result.args, ["git", "status"])
        self.assertEqual(result.stdout, "")
        self.assertIn("executable not found:", result.stderr)

    def test_run_command_returns_126_when_permission_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            with patch(
                "framework.scripts.lib.ci_helpers.subprocess.run",
                side_effect=PermissionError("Permission denied: 'git'"),
            ):
                result = ci_helpers.run_command(["git", "status"], cwd=cwd, timeout_sec=5)

        self.assertEqual(result.returncode, 126)
        self.assertEqual(result.args, ["git", "status"])
        self.assertEqual(result.stdout, "")
        self.assertIn("permission denied:", result.stderr)


if __name__ == "__main__":
    unittest.main()
