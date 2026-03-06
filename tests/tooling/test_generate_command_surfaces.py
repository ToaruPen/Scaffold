from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tooling/sync/generate_command_surfaces.py"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_command_surfaces_module", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class GenerateCommandSurfacesTests(unittest.TestCase):
    script: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.script = _load_script_module()

    def _run_script(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with (
            patch.object(sys, "argv", argv),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            exit_code = self.script.main()
        return exit_code, stdout.getvalue(), stderr.getvalue()

    def test_generates_core_only_by_default(self) -> None:
        manifest_text = """\
must_command_contracts:
  /research:
    requires: [research-before-spec]
  /pr-bots-review:
    requires: [pr-bot-iteration]
command_tiers:
  /research: core
  /pr-bots-review: conditional
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "manifest.yaml"
            output_root = tmp_path / "out"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            argv = [
                "generate_command_surfaces.py",
                "--manifest",
                str(manifest_path),
                "--output-root",
                str(output_root),
                "--agent",
                "all",
            ]

            exit_code, _, _ = self._run_script(argv)
            self.assertEqual(exit_code, 0)
            for agent in ("codex", "claude", "opencode"):
                payload = json.loads(
                    (output_root / f"{agent}.commands.json").read_text(encoding="utf-8")
                )
                self.assertEqual(payload["commands"], ["/research"])
                self.assertFalse(payload["policy"]["conditional_enabled"])

    def test_generates_conditional_when_enabled(self) -> None:
        manifest_text = """\
must_command_contracts:
  /research:
    requires: [research-before-spec]
  /waiver:
    requires: [waiver-exception]
command_tiers:
  /research: core
  /waiver: conditional
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "manifest.yaml"
            output_root = tmp_path / "out"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            argv = [
                "generate_command_surfaces.py",
                "--manifest",
                str(manifest_path),
                "--output-root",
                str(output_root),
                "--agent",
                "codex",
                "--enable-conditional",
            ]

            exit_code, _, _ = self._run_script(argv)
            self.assertEqual(exit_code, 0)
            payload = json.loads((output_root / "codex.commands.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["commands"], ["/research", "/waiver"])
            self.assertTrue(payload["policy"]["conditional_enabled"])

    def test_fails_when_must_command_has_no_tier(self) -> None:
        manifest_text = """\
must_command_contracts:
  /create-pr:
    requires: [pr-open-preconditions]
command_tiers:
  /research: core
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "manifest.yaml"
            output_root = tmp_path / "out"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            argv = [
                "generate_command_surfaces.py",
                "--manifest",
                str(manifest_path),
                "--output-root",
                str(output_root),
                "--agent",
                "claude",
            ]

            exit_code, _, stderr = self._run_script(argv)
            self.assertEqual(exit_code, 2)
            self.assertIn("must_command_contracts missing tier classification", stderr)
            self.assertFalse((output_root / "claude.commands.json").exists())

    def test_fails_on_malformed_manifest_yaml(self) -> None:
        manifest_text = """\
must_command_contracts:
  /create-pr:
    requires: [pr-open-preconditions]
command_tiers:
  /create-pr: core
  broken: [
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "manifest.yaml"
            output_root = tmp_path / "out"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            argv = [
                "generate_command_surfaces.py",
                "--manifest",
                str(manifest_path),
                "--output-root",
                str(output_root),
                "--agent",
                "claude",
            ]

            exit_code, _, stderr = self._run_script(argv)
            self.assertEqual(exit_code, 2)
            self.assertIn("failed to parse manifest YAML", stderr)
            self.assertFalse((output_root / "claude.commands.json").exists())

    def test_fails_when_command_tier_key_is_non_string(self) -> None:
        manifest_text = """\
must_command_contracts:
  /research:
    requires: [research-before-spec]
command_tiers:
  /research: core
  123: core
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "manifest.yaml"
            output_root = tmp_path / "out"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            argv = [
                "generate_command_surfaces.py",
                "--manifest",
                str(manifest_path),
                "--output-root",
                str(output_root),
                "--agent",
                "claude",
            ]

            exit_code, _, stderr = self._run_script(argv)
            self.assertEqual(exit_code, 2)
            self.assertIn("command_tiers contains invalid entries", stderr)
            self.assertFalse((output_root / "claude.commands.json").exists())

    def test_fails_when_must_command_key_is_non_string(self) -> None:
        manifest_text = """\
must_command_contracts:
  /research:
    requires: [research-before-spec]
  123:
    requires: [some-contract]
command_tiers:
  /research: core
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "manifest.yaml"
            output_root = tmp_path / "out"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            argv = [
                "generate_command_surfaces.py",
                "--manifest",
                str(manifest_path),
                "--output-root",
                str(output_root),
                "--agent",
                "claude",
            ]

            exit_code, _, stderr = self._run_script(argv)
            self.assertEqual(exit_code, 2)
            self.assertIn("must_command_contracts contains invalid entries: 123", stderr)
            self.assertFalse((output_root / "claude.commands.json").exists())

    def test_fails_with_exit_two_when_output_directory_creation_fails(self) -> None:
        manifest_text = """\
must_command_contracts:
  /research:
    requires: [research-before-spec]
command_tiers:
  /research: core
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "manifest.yaml"
            output_root = tmp_path / "out"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            argv = [
                "generate_command_surfaces.py",
                "--manifest",
                str(manifest_path),
                "--output-root",
                str(output_root),
                "--agent",
                "claude",
            ]

            with patch.object(self.script.Path, "mkdir", side_effect=OSError("permission denied")):
                exit_code, _, stderr = self._run_script(argv)
            self.assertEqual(exit_code, 2)
            self.assertIn("permission denied", stderr)
            self.assertFalse((output_root / "claude.commands.json").exists())

    def test_uses_profile_specific_default_output_directories(self) -> None:
        manifest_text = """\
must_command_contracts:
  /research:
    requires: [research-before-spec]
  /waiver:
    requires: [waiver-exception]
command_tiers:
  /research: core
  /waiver: conditional
"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            default_argv = [
                "generate_command_surfaces.py",
                "--manifest",
                str(manifest_path),
                "--agent",
                "claude",
            ]
            conditional_argv = [
                "generate_command_surfaces.py",
                "--manifest",
                str(manifest_path),
                "--agent",
                "claude",
                "--enable-conditional",
            ]

            old_cwd = Path.cwd()
            self.addCleanup(os.chdir, old_cwd)
            os.chdir(tmp_path)
            default_exit_code, _, _ = self._run_script(default_argv)
            conditional_exit_code, _, _ = self._run_script(conditional_argv)

            self.assertEqual(default_exit_code, 0)
            self.assertEqual(conditional_exit_code, 0)

            default_output = tmp_path / "tooling/sync/generated/default/claude.commands.json"
            conditional_output = (
                tmp_path / "tooling/sync/generated/with-conditional/claude.commands.json"
            )

            self.assertTrue(default_output.exists())
            self.assertTrue(conditional_output.exists())

            default_payload = json.loads(default_output.read_text(encoding="utf-8"))
            conditional_payload = json.loads(conditional_output.read_text(encoding="utf-8"))
            self.assertEqual(default_payload["commands"], ["/research"])
            self.assertEqual(conditional_payload["commands"], ["/research", "/waiver"])


if __name__ == "__main__":
    unittest.main()
