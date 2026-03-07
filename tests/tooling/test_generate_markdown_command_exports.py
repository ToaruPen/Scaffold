from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast
from unittest.mock import patch

from tooling.sync.lib.command_surface_loader import CommandSurfaceLoadError, load_command_catalog

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "tooling/sync/generate_markdown_command_exports.py"
FIXTURE_BUILDER_PATH = Path(__file__).resolve().parent / "manifest_fixture_builder.py"


def _load_script_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "generate_markdown_command_exports_module", SCRIPT_PATH
    )
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


def _active_root(repo_root: Path) -> Path:
    return repo_root / "framework"


def _active_opencode_path(repo_root: Path, slug: str) -> Path:
    return _active_root(repo_root) / ".opencode/commands" / f"{slug}.md"


def _active_claude_path(repo_root: Path, slug: str) -> Path:
    return _active_root(repo_root) / ".claude/skills" / slug / "SKILL.md"


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
            research_path = _active_opencode_path(repo_root, "research")
            self.assertTrue(research_path.exists())
            content = research_path.read_text(encoding="utf-8")
            self.assertIn('description: "Summary for /research"', content)
            self.assertIn("# /research", content)
            self.assertIn("`research-before-spec`", content)
            self.assertIn("- `manifest.yaml`", content)

    def test_quotes_frontmatter_description_for_yaml_special_characters(self) -> None:
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
command_metadata:
  /research:
    summary: "Hello: world"
    when_to_use: When to use /research
    next_steps:
      - /research
"""
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
            content = _active_opencode_path(repo_root, "research").read_text(encoding="utf-8")
            self.assertIn('description: "Hello: world"', content)

    def test_resolves_relative_repo_root_from_current_working_directory(self) -> None:
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
            repo_root = tmp_path / "repo"
            repo_root.mkdir()
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            old_cwd = Path.cwd()
            self.addCleanup(os.chdir, old_cwd)
            os.chdir(tmp_path)
            exit_code, _, _ = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    "repo",
                    "--manifest",
                    "repo/manifest.yaml",
                    "--agent",
                    "opencode",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(_active_opencode_path(repo_root, "research").exists())

    def test_resolves_relative_manifest_from_current_working_directory(self) -> None:
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
            repo_root = tmp_path / "repo"
            repo_root.mkdir()
            cwd_path = repo_root / "cwd"
            cwd_path.mkdir()
            manifest_path = cwd_path / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            old_cwd = Path.cwd()
            self.addCleanup(os.chdir, old_cwd)
            os.chdir(cwd_path)
            exit_code, _, _ = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    "manifest.yaml",
                    "--agent",
                    "opencode",
                ]
            )

            self.assertEqual(exit_code, 0)
            content = _active_opencode_path(repo_root, "research").read_text(encoding="utf-8")
            self.assertIn("cwd/manifest.yaml`", content)

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
            content = _active_opencode_path(repo_root, "create-pr").read_text(encoding="utf-8")
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
            skill_path = _active_claude_path(repo_root, "worktree")
            self.assertTrue(skill_path.exists())
            content = skill_path.read_text(encoding="utf-8")
            self.assertIn("name: worktree", content)
            self.assertIn(
                (
                    'description: "Handles Scaffold `/worktree` contract guidance '
                    'and required evidence."'
                ),
                content,
            )
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
            root_opencode = _active_opencode_path(repo_root, "research")
            root_opencode.parent.mkdir(parents=True, exist_ok=True)
            root_opencode.write_text("manual root command\n", encoding="utf-8")

            exit_code, _, _ = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--output-root",
                    str(repo_root / "tooling/sync/generated/with-conditional/markdown"),
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

    def test_refuses_downgrading_live_conditional_surface_without_force(self) -> None:
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
            conditional_path = _active_opencode_path(repo_root, "pr-bots-review")
            conditional_path.parent.mkdir(parents=True, exist_ok=True)
            conditional_path.write_text(
                "---\ndescription: generated\n---\n\n"
                + self.script.GENERATED_HEADER
                + "\n\nExisting conditional command\n",
                encoding="utf-8",
            )

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
            self.assertIn("live conditional markdown surfaces already exist", stderr)

    def test_enable_conditional_writes_to_root_surfaces(self) -> None:
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
                    "all",
                    "--enable-conditional",
                    "--write-active-surfaces",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(_active_opencode_path(repo_root, "pr-bots-review").exists())
            self.assertTrue(_active_claude_path(repo_root, "pr-bots-review").exists())
            create_pr = _active_opencode_path(repo_root, "create-pr").read_text(encoding="utf-8")
            self.assertIn("`/pr-bots-review`", create_pr)

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

    def test_force_overwrite_allows_removing_stale_manual_files(self) -> None:
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
            stale_manual = _active_opencode_path(repo_root, "obsolete")
            stale_manual.parent.mkdir(parents=True, exist_ok=True)
            stale_manual.write_text("manual stale\n", encoding="utf-8")

            exit_code, _, _ = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--agent",
                    "opencode",
                    "--force-overwrite-existing",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertFalse(stale_manual.exists())

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
            stale_path = _active_opencode_path(repo_root, "old")
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
            manual_path = _active_opencode_path(repo_root, "research")
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

    def test_banner_text_inside_manual_file_is_not_treated_as_generated(self) -> None:
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
            manual_path = _active_opencode_path(repo_root, "research")
            manual_path.parent.mkdir(parents=True, exist_ok=True)
            manual_path.write_text(
                f"Manual note mentioning {self.script.GENERATED_HEADER}\n",
                encoding="utf-8",
            )

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

    def test_stale_manual_conflict_fails_before_writing_new_outputs(self) -> None:
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
            desired_generated = _active_opencode_path(repo_root, "research")
            desired_generated.parent.mkdir(parents=True, exist_ok=True)
            desired_generated.write_text(
                "---\ndescription: generated\n---\n\n"
                + self.script.GENERATED_HEADER
                + "\n\nOriginal generated content\n",
                encoding="utf-8",
            )
            stale_manual = _active_opencode_path(repo_root, "obsolete")
            stale_manual.write_text("manual stale\n", encoding="utf-8")

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
            self.assertIn("is stale but not generated", stderr)
            self.assertEqual(
                desired_generated.read_text(encoding="utf-8"),
                "---\ndescription: generated\n---\n\n"
                + self.script.GENERATED_HEADER
                + "\n\nOriginal generated content\n",
            )

    def test_agent_all_fails_before_any_agent_writes(self) -> None:
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
            opencode_target = _active_opencode_path(repo_root, "research")
            opencode_target.parent.mkdir(parents=True, exist_ok=True)
            opencode_target.write_text("manual\n", encoding="utf-8")

            exit_code, _, stderr = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--agent",
                    "all",
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("refusing to overwrite without --force-overwrite-existing", stderr)
            self.assertFalse(_active_claude_path(repo_root, "research").exists())

    def test_repository_generated_markdown_exports_are_in_sync(self) -> None:
        catalog = load_command_catalog(REPO_ROOT, REPO_ROOT / "framework/scripts/manifest.yaml")
        active_commands = catalog["commands"]
        conditional_commands = catalog["commands"]

        with tempfile.TemporaryDirectory() as tmp:
            active_repo_root = Path(tmp) / "active-root"
            conditional_output_root = Path(tmp) / "markdown-preview-conditional"
            active_repo_root.mkdir()
            active_manifest = active_repo_root / "framework/scripts/manifest.yaml"
            active_manifest.parent.mkdir(parents=True, exist_ok=True)
            active_manifest.write_text(
                (REPO_ROOT / "framework/scripts/manifest.yaml").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            exit_code, _, _ = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(active_repo_root),
                    "--agent",
                    "all",
                    "--enable-conditional",
                    "--write-active-surfaces",
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
            for command in active_commands:
                opencode_expected = (
                    _active_opencode_path(active_repo_root, command["slug"])
                ).read_text(encoding="utf-8")
                opencode_actual = (_active_opencode_path(REPO_ROOT, command["slug"])).read_text(
                    encoding="utf-8"
                )
                self.assertEqual(opencode_actual, opencode_expected)

                claude_expected = (
                    _active_claude_path(active_repo_root, command["slug"])
                ).read_text(encoding="utf-8")
                claude_actual = (_active_claude_path(REPO_ROOT, command["slug"])).read_text(
                    encoding="utf-8"
                )
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

    def test_refuses_filesystem_root_output_root(self) -> None:
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
                    "/",
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("must not point at the filesystem root", stderr)

    def test_refuses_combining_output_root_with_active_surface_install(self) -> None:
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
                    str(repo_root / "preview"),
                    "--write-active-surfaces",
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("cannot be combined with --output-root", stderr)

    def test_refuses_sync_preview_snapshot_without_active_surface_flag(self) -> None:
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
                    "--enable-conditional",
                    "--sync-preview-snapshot",
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("requires --write-active-surfaces", stderr)

    def test_sync_preview_snapshot_preflights_preview_before_live_writes(self) -> None:
        manifest_text = build_manifest(
            [
                {
                    "id": "/research",
                    "tier": "core",
                    "requires": ["research-before-spec"],
                    "next_steps": ["/research"],
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
            preview_conflict = (
                repo_root
                / "tooling/sync/generated/with-conditional/markdown/opencode"
                / ".opencode/commands/obsolete.md"
            )
            preview_conflict.parent.mkdir(parents=True, exist_ok=True)
            preview_conflict.write_text("manual stale\n", encoding="utf-8")

            exit_code, _, stderr = self._run_script(
                [
                    "generate_markdown_command_exports.py",
                    "--repo-root",
                    str(repo_root),
                    "--manifest",
                    str(manifest_path),
                    "--agent",
                    "all",
                    "--enable-conditional",
                    "--write-active-surfaces",
                    "--sync-preview-snapshot",
                ]
            )

            self.assertEqual(exit_code, 2)
            self.assertIn("is stale but not generated", stderr)
            self.assertFalse(_active_opencode_path(repo_root, "research").exists())

    def test_sync_preview_snapshot_applies_preview_before_live_outputs(self) -> None:
        manifest_text = build_manifest(
            [
                {
                    "id": "/research",
                    "tier": "core",
                    "requires": ["research-before-spec"],
                    "next_steps": ["/research"],
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

            original_apply = self.script._apply_agent_output_plan

            def fail_preview_first(
                *,
                rendered_outputs: list[tuple[Path, str]],
                stale_paths: list[Path],
                output_base: Path,
            ) -> list[Path]:
                if "tooling/sync/generated/with-conditional/markdown" in output_base.as_posix():
                    raise CommandSurfaceLoadError("preview write failed")
                return cast(
                    list[Path],
                    original_apply(
                        rendered_outputs=rendered_outputs,
                        stale_paths=stale_paths,
                        output_base=output_base,
                    ),
                )

            with patch.object(
                self.script, "_apply_agent_output_plan", side_effect=fail_preview_first
            ):
                exit_code, _, stderr = self._run_script(
                    [
                        "generate_markdown_command_exports.py",
                        "--repo-root",
                        str(repo_root),
                        "--manifest",
                        str(manifest_path),
                        "--agent",
                        "all",
                        "--enable-conditional",
                        "--write-active-surfaces",
                        "--sync-preview-snapshot",
                    ]
                )

            self.assertEqual(exit_code, 2)
            self.assertIn("preview write failed", stderr)
            self.assertFalse(_active_opencode_path(repo_root, "research").exists())


if __name__ == "__main__":
    unittest.main()
