from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tooling/sync/generate_command_surfaces.py"
FIXTURE_BUILDER_PATH = Path(__file__).resolve().parent / "manifest_fixture_builder.py"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_command_surfaces_module", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_manifest_builder() -> Callable[..., str]:
    spec = importlib.util.spec_from_file_location(
        "manifest_fixture_builder_module", FIXTURE_BUILDER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(Callable[..., str], module.build_manifest)


build_manifest: Callable[..., str] = _load_manifest_builder()


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
        manifest_text = build_manifest(
            [
                {
                    "id": "/pr-bots-review",
                    "tier": "conditional",
                    "requires": ["pr-bot-iteration"],
                    "next_steps": ["/research"],
                },
                {
                    "id": "/research",
                    "tier": "core",
                    "requires": ["research-before-spec"],
                    "next_steps": ["/create-prd"],
                },
                {
                    "id": "/create-prd",
                    "tier": "core",
                    "requires": ["spec-quality-minimum"],
                    "next_steps": ["/research"],
                },
            ]
        )
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
                self.assertEqual(payload["commands"], ["/create-prd", "/research"])
                self.assertFalse(payload["policy"]["conditional_enabled"])

    def test_generates_conditional_when_enabled(self) -> None:
        manifest_text = build_manifest(
            [
                {
                    "id": "/research",
                    "tier": "core",
                    "requires": ["research-before-spec"],
                    "next_steps": ["/waiver"],
                },
                {
                    "id": "/waiver",
                    "tier": "conditional",
                    "requires": ["waiver-exception"],
                    "next_steps": ["/research"],
                },
            ]
        )
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
contracts:
  - id: pr-open-preconditions
    description: pr-open-preconditions description
    validator: framework/scripts/gates/pr-open-preconditions.py
must_command_contracts:
  /create-pr:
    requires:
      - pr-open-preconditions
command_tiers:
  /research: core
command_metadata:
  /research:
    summary: Summary for /research
    when_to_use: When to use /research
    next_steps:
      - /research
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

    def test_allows_missing_command_metadata_for_json_surface_generation(self) -> None:
        manifest_text = build_manifest(
            [
                {
                    "id": "/research",
                    "tier": "core",
                    "requires": ["research-before-spec"],
                    "next_steps": ["/research"],
                }
            ],
            include_metadata=False,
        )
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
            self.assertEqual(exit_code, 0)
            payload = json.loads((output_root / "claude.commands.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["commands"], ["/research"])

    def test_fails_on_malformed_manifest_yaml(self) -> None:
        manifest_text = """\
contracts:
  - id: pr-open-preconditions
    description: pr-open-preconditions description
    validator: framework/scripts/gates/pr-open-preconditions.py
must_command_contracts:
  /create-pr:
    requires:
      - pr-open-preconditions
command_tiers:
  /create-pr: core
command_metadata:
  /create-pr:
    summary: Summary for /create-pr
    when_to_use: When to use /create-pr
    next_steps:
      - /create-pr
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
            self.assertIn("failed to parse manifest yaml", stderr)
            self.assertFalse((output_root / "claude.commands.json").exists())

    def test_fails_when_command_tier_key_is_non_string(self) -> None:
        manifest_text = """\
contracts:
  - id: research-before-spec
    description: research-before-spec description
    validator: framework/scripts/gates/research-before-spec.py
must_command_contracts:
  /research:
    requires:
      - research-before-spec
command_tiers:
  /research: core
  123: core
command_metadata:
  /research:
    summary: Summary for /research
    when_to_use: When to use /research
    next_steps:
      - /research
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
contracts:
  - id: research-before-spec
    description: research-before-spec description
    validator: framework/scripts/gates/research-before-spec.py
must_command_contracts:
  /research:
    requires:
      - research-before-spec
  123:
    requires:
      - some-contract
command_tiers:
  /research: core
command_metadata:
  /research:
    summary: Summary for /research
    when_to_use: When to use /research
    next_steps:
      - /research
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
        manifest_text = build_manifest(
            [
                {
                    "id": "/research",
                    "tier": "core",
                    "requires": ["research-before-spec"],
                    "next_steps": ["/research"],
                }
            ]
        )
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
        manifest_text = build_manifest(
            [
                {
                    "id": "/research",
                    "tier": "core",
                    "requires": ["research-before-spec"],
                    "next_steps": ["/waiver"],
                },
                {
                    "id": "/waiver",
                    "tier": "conditional",
                    "requires": ["waiver-exception"],
                    "next_steps": ["/research"],
                },
            ]
        )
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

    def test_repository_generated_command_surfaces_are_in_sync(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            default_output_root = tmp_path / "default"
            conditional_output_root = tmp_path / "conditional"

            default_exit_code, _, _ = self._run_script(
                [
                    "generate_command_surfaces.py",
                    "--output-root",
                    str(default_output_root),
                    "--agent",
                    "all",
                ]
            )
            conditional_exit_code, _, _ = self._run_script(
                [
                    "generate_command_surfaces.py",
                    "--output-root",
                    str(conditional_output_root),
                    "--agent",
                    "all",
                    "--enable-conditional",
                ]
            )

            self.assertEqual(default_exit_code, 0)
            self.assertEqual(conditional_exit_code, 0)

            for profile_name, output_root in (
                ("default", default_output_root),
                ("with-conditional", conditional_output_root),
            ):
                for agent in ("codex", "claude", "opencode"):
                    expected = (output_root / f"{agent}.commands.json").read_text(encoding="utf-8")
                    actual = (
                        REPO_ROOT / f"tooling/sync/generated/{profile_name}/{agent}.commands.json"
                    ).read_text(encoding="utf-8")
                    self.assertEqual(actual, expected)

    def test_relative_manifest_path_is_resolved_from_current_working_directory(self) -> None:
        manifest_text = build_manifest(
            [
                {
                    "id": "/research",
                    "tier": "core",
                    "requires": ["research-before-spec"],
                    "next_steps": ["/research"],
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            manifest_path = tmp_path / "manifest.yaml"
            output_root = tmp_path / "out"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            old_cwd = Path.cwd()
            self.addCleanup(os.chdir, old_cwd)
            os.chdir(tmp_path)
            exit_code, _, _ = self._run_script(
                [
                    "generate_command_surfaces.py",
                    "--manifest",
                    "manifest.yaml",
                    "--output-root",
                    str(output_root),
                    "--agent",
                    "claude",
                ]
            )

            self.assertEqual(exit_code, 0)
            payload = json.loads((output_root / "claude.commands.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["source_manifest"], "manifest.yaml")


if __name__ == "__main__":
    unittest.main()
