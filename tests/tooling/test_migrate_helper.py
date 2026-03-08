from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tooling/migrate/migrate_helper.py"

sys.path.insert(0, str(REPO_ROOT))

from tooling.migrate.lib.conflict_detector import ConflictResult, detect_conflicts  # noqa: E402
from tooling.migrate.lib.path_mapper import MappingResult, find_mappable_files  # noqa: E402
from tooling.migrate.lib.report_formatter import format_report  # noqa: E402


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migrate_helper_module", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PathMapperTests(unittest.TestCase):
    def test_find_mappable_files_empty_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = find_mappable_files(Path(tmp))
            self.assertEqual(result, [])

    def test_find_mappable_files_with_old_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            gate_dir = tmp_path / "scripts" / "gates"
            gate_dir.mkdir(parents=True)
            (gate_dir / "validate_foo.py").write_text("# gate\n", encoding="utf-8")

            result = find_mappable_files(tmp_path)
            self.assertEqual(len(result), 1)
            self.assertIsInstance(result[0], MappingResult)
            self.assertEqual(result[0].old_path, "scripts/gates/validate_foo.py")
            self.assertEqual(result[0].new_path, "framework/scripts/gates/validate_foo.py")
            self.assertEqual(result[0].action, "migrate")


class ConflictDetectorTests(unittest.TestCase):
    def test_detect_conflicts_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "target"
            framework = tmp_path / "framework"
            target.mkdir()
            framework.mkdir()
            (target / "app.py").write_text("# app\n", encoding="utf-8")
            (framework / "lib.py").write_text("# lib\n", encoding="utf-8")

            result = detect_conflicts(target, framework)
            self.assertEqual(result, [])

    def test_detect_conflicts_with_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "target"
            framework = tmp_path / "framework"
            target.mkdir()
            framework.mkdir()
            (target / "README.md").write_text("# target\n", encoding="utf-8")
            (framework / "README.md").write_text("# framework\n", encoding="utf-8")

            result = detect_conflicts(target, framework)
            self.assertEqual(len(result), 1)
            self.assertIsInstance(result[0], ConflictResult)
            self.assertEqual(result[0].path, "README.md")
            self.assertEqual(result[0].conflict_type, "file_exists")


class ReportFormatterTests(unittest.TestCase):
    def test_format_report_empty(self) -> None:
        report = format_report([], [])
        self.assertIn("No mappable files found.", report)
        self.assertIn("No conflicts found.", report)
        self.assertIn("No manual fixes required.", report)

    def test_format_report_with_data(self) -> None:
        mappings = [
            MappingResult(
                "scripts/gates/check.py",
                "framework/scripts/gates/check.py",
                "migrate",
            ),
        ]
        conflicts = [
            ConflictResult(
                "README.md",
                "file_exists",
                "Target already has file at framework path: README.md",
            ),
        ]
        report = format_report(mappings, conflicts)
        self.assertIn("## Summary", report)
        self.assertIn("## File Mappings", report)
        self.assertIn("## Conflicts", report)
        self.assertIn("## Required Manual Fixes", report)
        self.assertIn("scripts/gates/check.py", report)
        self.assertIn("README.md", report)


class MigrateHelperCLITests(unittest.TestCase):
    script: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.script = _load_script_module()

    def test_cli_help(self) -> None:
        with patch.object(sys, "argv", ["migrate_helper.py", "--help"]):
            stdout = io.StringIO()
            with (
                contextlib.redirect_stdout(stdout),
                self.assertRaises(SystemExit) as cm,
            ):
                self.script.main()
            self.assertEqual(cm.exception.code, 0)
            self.assertIn("usage:", stdout.getvalue().lower())

    def test_cli_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "target"
            target.mkdir()
            scaffold = tmp_path / "scaffold"
            scaffold.mkdir()
            (scaffold / "framework").mkdir()
            output_file = tmp_path / "report.txt"

            argv = [
                "migrate_helper.py",
                "--target-repo",
                str(target),
                "--scaffold-repo",
                str(scaffold),
                "--output",
                str(output_file),
            ]

            with patch.object(sys, "argv", argv):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    exit_code = self.script.main()

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_file.exists())
            content = output_file.read_text(encoding="utf-8")
            self.assertIn("Migration Analysis Report", content)

    def test_cli_nonexistent_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            scaffold = tmp_path / "scaffold"
            scaffold.mkdir()
            (scaffold / "framework").mkdir()

            argv = [
                "migrate_helper.py",
                "--target-repo",
                "/nonexistent_scaffold_test_path",
                "--scaffold-repo",
                str(scaffold),
            ]

            with patch.object(sys, "argv", argv):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    exit_code = self.script.main()

            self.assertEqual(exit_code, 2)
            self.assertIn("does not exist", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
