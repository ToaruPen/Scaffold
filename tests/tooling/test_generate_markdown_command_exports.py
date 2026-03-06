from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from tooling.sync.lib.command_surface_loader import load_command_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tooling/sync/generate_markdown_command_exports.py"
FIXTURE_BUILDER_PATH = Path(__file__).resolve().parent / "manifest_fixture_builder.py"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_markdown_command_exports_module", SCRIPT_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_manifest_builder() -> Callable[..., str]:
    spec = importlib.util.spec_from_file_location(
        "manifest_fixture_builder_module", FIXTURE_BUILDER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_manifest


build_manifest: Callable[..., str] = _load_manifest_builder()


class GenerateMarkdownCommandExportsTests(unittest.TestCase):
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

    def test_generates_root_level_opencode_commands(self) -> None:
        manifest_text = build_manifest(
            [
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
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            exit_code, _, _ = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--agent",
                    "opencode",
                ]
            )

            self.assertEqual(exit_code, 0)
            research_path = repo_root / ".opencode/commands/research.md"
            self.assertTrue(research_path.exists())
            content = research_path.read_text(encoding="utf-8")
            self.assertIn("description: Summary for /research", content)
            self.assertIn("# /research", content)
            self.assertIn("`research-before-spec`", content)
            self.assertIn("- `manifest.yaml`", content)

    def test_filters_conditional_next_steps_from_root_core_exports(self) -> None:
        manifest_text = build_manifest(
            [
                {
                    "id": "/create-pr",
                    "tier": "core",
                    "requires": ["pr-open-preconditions"],
                    "next_steps": ["/pr-bots-review"],
                },
                {
                    "id": "/pr-bots-review",
                    "tier": "conditional",
                    "requires": ["pr-bot-iteration"],
                    "next_steps": ["/create-pr"],
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            exit_code, _, _ = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--agent",
                    "opencode",
                ]
            )

            self.assertEqual(exit_code, 0)
            content = (repo_root / ".opencode/commands/create-pr.md").read_text(encoding="utf-8")
            self.assertIn("## Next Commands", content)
            self.assertNotIn("`/pr-bots-review`", content)

    def test_generates_root_level_claude_skills(self) -> None:
        manifest_text = build_manifest(
            [
                {
                    "id": "/worktree",
                    "tier": "core",
                    "requires": ["scope-lock"],
                    "next_steps": ["/estimation"],
                },
                {
                    "id": "/estimation",
                    "tier": "core",
                    "requires": ["estimate-approval"],
                    "next_steps": ["/worktree"],
                },
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            exit_code, _, _ = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--agent",
                    "claude",
                ]
            )

            self.assertEqual(exit_code, 0)
            skill_path = repo_root / ".claude/skills/worktree/SKILL.md"
            self.assertTrue(skill_path.exists())
            content = skill_path.read_text(encoding="utf-8")
            self.assertIn("name: worktree", content)
            self.assertIn("description: Handles Scaffold `/worktree` contract guidance", content)
            self.assertIn("## Required Contracts", content)

    def test_generates_conditional_preview_without_touching_root_outputs(self) -> None:
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
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")
            root_opencode = repo_root / ".opencode/commands/research.md"
            root_opencode.parent.mkdir(parents=True, exist_ok=True)
            root_opencode.write_text("manual root command\n", encoding="utf-8")

            exit_code, _, _ = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--enable-conditional",
                    "--agent",
                    "opencode",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(root_opencode.read_text(encoding="utf-8"), "manual root command\n")
            preview_path = (
                repo_root
                / "tooling/sync/generated/with-conditional/markdown/opencode"
                / ".opencode/commands/waiver.md"
            )
            self.assertTrue(preview_path.exists())

    def test_output_root_preserves_unrelated_existing_files(self) -> None:
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
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            preview_root = repo_root / "preview"
            manifest_path.write_text(manifest_text, encoding="utf-8")
            unrelated = preview_root / "notes/manual.txt"
            unrelated.parent.mkdir(parents=True, exist_ok=True)
            unrelated.write_text("keep me\n", encoding="utf-8")

            exit_code, _, _ = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--output-root",
                    str(preview_root),
                    "--agent",
                    "opencode",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep me\n")

    def test_output_root_refuses_overwriting_manual_target_without_force(self) -> None:
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
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            preview_root = repo_root / "preview"
            manifest_path.write_text(manifest_text, encoding="utf-8")
            target = preview_root / "opencode/.opencode/commands/research.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("manual preview\n", encoding="utf-8")

            exit_code, _, stderr = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--output-root",
                    str(preview_root),
                    "--agent",
                    "opencode",
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("refusing to overwrite without --force-overwrite-existing", stderr)

    def test_removes_stale_generated_files(self) -> None:
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
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")
            stale_path = repo_root / ".opencode/commands/old.md"
            stale_path.parent.mkdir(parents=True, exist_ok=True)
            stale_path.write_text(
                "---\ndescription: stale\n---\n\n" + self.script.GENERATED_HEADER + "\n",
                encoding="utf-8",
            )

            exit_code, _, _ = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--agent",
                    "opencode",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertFalse(stale_path.exists())

    def test_refuses_to_overwrite_manual_non_generated_file(self) -> None:
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
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")
            manual_path = repo_root / ".opencode/commands/research.md"
            manual_path.parent.mkdir(parents=True, exist_ok=True)
            manual_path.write_text("manual\n", encoding="utf-8")

            exit_code, _, stderr = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--agent",
                    "opencode",
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("refusing to overwrite without --force-overwrite-existing", stderr)

    def test_repository_generated_markdown_exports_are_in_sync(self) -> None:
        catalog = load_command_catalog(REPO_ROOT, REPO_ROOT / "framework/scripts/manifest.yaml")
        core_commands = [command for command in catalog["commands"] if command["tier"] == "core"]
        conditional_commands = catalog["commands"]

        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "markdown-preview"
            conditional_output_root = Path(tmp) / "markdown-preview-conditional"
            exit_code, _, _ = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--output-root",
                    str(output_root),
                    "--agent",
                    "all",
                ]
            )
            conditional_exit_code, _, _ = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--output-root",
                    str(conditional_output_root),
                    "--agent",
                    "all",
                    "--enable-conditional",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(conditional_exit_code, 0)
            for command in core_commands:
                opencode_expected = (
                    output_root / "opencode/.opencode/commands" / f"{command['slug']}.md"
                ).read_text(encoding="utf-8")
                opencode_actual = (
                    REPO_ROOT / ".opencode/commands" / f"{command['slug']}.md"
                ).read_text(encoding="utf-8")
                self.assertEqual(opencode_actual, opencode_expected)

                claude_expected = (
                    output_root / "claude/.claude/skills" / command["slug"] / "SKILL.md"
                ).read_text(encoding="utf-8")
                claude_actual = (
                    REPO_ROOT / ".claude/skills" / command["slug"] / "SKILL.md"
                ).read_text(encoding="utf-8")
                self.assertEqual(claude_actual, claude_expected)

            for command in conditional_commands:
                preview_opencode_expected = (
                    conditional_output_root
                    / "opencode/.opencode/commands"
                    / f"{command['slug']}.md"
                ).read_text(encoding="utf-8")
                preview_opencode_actual = (
                    REPO_ROOT
                    / "tooling/sync/generated/with-conditional/markdown/opencode/.opencode/commands"
                    / f"{command['slug']}.md"
                ).read_text(encoding="utf-8")
                self.assertEqual(preview_opencode_actual, preview_opencode_expected)

                preview_claude_expected = (
                    conditional_output_root / "claude/.claude/skills" / command["slug"] / "SKILL.md"
                ).read_text(encoding="utf-8")
                preview_claude_actual = (
                    REPO_ROOT
                    / "tooling/sync/generated/with-conditional/markdown/claude/.claude/skills"
                    / command["slug"]
                    / "SKILL.md"
                ).read_text(encoding="utf-8")
                self.assertEqual(preview_claude_actual, preview_claude_expected)

    def test_refuses_dangerous_output_root(self) -> None:
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
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            exit_code, _, stderr = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--output-root",
                    str(repo_root),
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("must not point at the repository root", stderr)


if __name__ == "__main__":
    unittest.main()
