from __future__ import annotations

import contextlib
import importlib.util
import io
import json
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

            with patch.object(sys, "argv", argv):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exit_code = self.script.main()

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

            with patch.object(sys, "argv", argv):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exit_code = self.script.main()

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

            with patch.object(sys, "argv", argv):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exit_code = self.script.main()

            self.assertEqual(exit_code, 2)
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

            with patch.object(sys, "argv", argv):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exit_code = self.script.main()

            self.assertEqual(exit_code, 2)
            self.assertFalse((output_root / "claude.commands.json").exists())


if __name__ == "__main__":
    unittest.main()
