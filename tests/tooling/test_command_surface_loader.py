from __future__ import annotations

import importlib.util
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import cast

from tooling.sync.lib.command_surface_loader import (
    CommandSurfaceLoadError,
    load_command_catalog,
)

FIXTURE_BUILDER_PATH = Path(__file__).resolve().parent / "manifest_fixture_builder.py"


def _load_manifest_builder() -> Callable[..., str]:
    spec = importlib.util.spec_from_file_location(
        "manifest_fixture_builder_module", FIXTURE_BUILDER_PATH
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(Callable[..., str], module.build_manifest)


build_manifest: Callable[..., str] = _load_manifest_builder()


class CommandSurfaceLoaderTests(unittest.TestCase):
    def test_loads_catalog_with_required_contract_details(self) -> None:
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

            catalog = load_command_catalog(repo_root, manifest_path)

            self.assertEqual(catalog["tiers"]["core"], ["/create-prd", "/research"])
            self.assertEqual(catalog["tiers"]["conditional"], [])
            research = next(
                command for command in catalog["commands"] if command["id"] == "/research"
            )
            self.assertEqual(catalog["manifest_path"], "manifest.yaml")
            self.assertEqual(research["slug"], "research")
            self.assertEqual(research["required_contracts"][0]["id"], "research-before-spec")

    def test_normalizes_external_manifest_path_to_filename(self) -> None:
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
            temp_root = Path(tmp)
            repo_root = temp_root / "repo"
            repo_root.mkdir()
            manifest_path = temp_root / "outside.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            with self.assertRaisesRegex(
                CommandSurfaceLoadError, "manifest_path must stay within repo_root"
            ):
                load_command_catalog(repo_root, manifest_path)

    def test_rejects_relative_manifest_escape_outside_repo_root(self) -> None:
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
            temp_root = Path(tmp)
            repo_root = temp_root / "repo"
            repo_root.mkdir()
            outside_manifest = temp_root / "outside.yaml"
            outside_manifest.write_text(manifest_text, encoding="utf-8")

            with self.assertRaisesRegex(
                CommandSurfaceLoadError, "manifest_path must stay within repo_root"
            ):
                load_command_catalog(repo_root, Path("../outside.yaml"))

    def test_fails_when_command_metadata_entry_is_missing(self) -> None:
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
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            with self.assertRaisesRegex(
                CommandSurfaceLoadError, "command_metadata must be a mapping"
            ):
                load_command_catalog(repo_root, manifest_path)

    def test_fails_when_command_metadata_key_is_non_string(self) -> None:
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
    summary: Summary for /research
    when_to_use: When to use /research
    next_steps:
      - /research
  123:
    summary: Summary for bad key
    when_to_use: When to use bad key
    next_steps:
      - /research
"""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            with self.assertRaisesRegex(
                CommandSurfaceLoadError, "command_metadata contains invalid entries: 123"
            ):
                load_command_catalog(repo_root, manifest_path)

    def test_fails_when_command_id_contains_nested_path_segments(self) -> None:
        manifest_text = """\
contracts:
  - id: research-before-spec
    description: research-before-spec description
    validator: framework/scripts/gates/research-before-spec.py
must_command_contracts:
  /research/nested:
    requires:
      - research-before-spec
command_tiers:
  /research/nested: core
command_metadata:
  /research/nested:
    summary: Summary for /research/nested
    when_to_use: When to use /research/nested
    next_steps:
      - /research/nested
"""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            with self.assertRaisesRegex(
                CommandSurfaceLoadError,
                "must_command_contracts contains invalid entries: /research/nested",
            ):
                load_command_catalog(repo_root, manifest_path)

    def test_fails_when_command_tier_key_contains_path_traversal(self) -> None:
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
  /../research: core
command_metadata:
  /research:
    summary: Summary for /research
    when_to_use: When to use /research
    next_steps:
      - /research
"""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            with self.assertRaisesRegex(
                CommandSurfaceLoadError,
                r"command_tiers contains invalid entries: /\.\./research",
            ):
                load_command_catalog(repo_root, manifest_path)

    def test_fails_when_command_slugs_collide_case_insensitively(self) -> None:
        manifest_text = """\
contracts:
  - id: research-before-spec
    description: research-before-spec description
    validator: framework/scripts/gates/research-before-spec.py
must_command_contracts:
  /Foo:
    requires:
      - research-before-spec
  /foo:
    requires:
      - research-before-spec
command_tiers:
  /Foo: core
  /foo: core
command_metadata:
  /Foo:
    summary: Summary for /Foo
    when_to_use: When to use /Foo
    next_steps:
      - /Foo
  /foo:
    summary: Summary for /foo
    when_to_use: When to use /foo
    next_steps:
      - /foo
"""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            with self.assertRaisesRegex(
                CommandSurfaceLoadError,
                r"command_tiers contains slug collisions: /Foo, /foo",
            ):
                load_command_catalog(repo_root, manifest_path)

    def test_fails_when_windows_reserved_slug_is_used(self) -> None:
        manifest_text = """\
contracts:
  - id: research-before-spec
    description: research-before-spec description
    validator: framework/scripts/gates/research-before-spec.py
must_command_contracts:
  /CON:
    requires:
      - research-before-spec
command_tiers:
  /CON: core
command_metadata:
  /CON:
    summary: Summary for /CON
    when_to_use: When to use /CON
    next_steps:
      - /CON
"""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            with self.assertRaisesRegex(
                CommandSurfaceLoadError,
                r"must_command_contracts contains invalid entries: /CON",
            ):
                load_command_catalog(repo_root, manifest_path)

    def test_fails_when_slug_collides_across_catalog_sections(self) -> None:
        manifest_text = """\
contracts:
  - id: research-before-spec
    description: research-before-spec description
    validator: framework/scripts/gates/research-before-spec.py
must_command_contracts:
  /Foo:
    requires:
      - research-before-spec
command_tiers:
  /foo: core
command_metadata:
  /foo:
    summary: Summary for /foo
    when_to_use: When to use /foo
    next_steps:
      - /foo
"""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            with self.assertRaisesRegex(
                CommandSurfaceLoadError,
                r"command_catalog contains slug collisions: /Foo, /foo",
            ):
                load_command_catalog(repo_root, manifest_path)

    def test_fails_when_next_step_references_unknown_command(self) -> None:
        manifest_text = build_manifest(
            [
                {
                    "id": "/research",
                    "tier": "core",
                    "requires": ["research-before-spec"],
                    "next_steps": ["/missing"],
                }
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            with self.assertRaisesRegex(CommandSurfaceLoadError, "unknown commands"):
                load_command_catalog(repo_root, manifest_path)

    def test_fails_when_required_contract_definition_is_missing(self) -> None:
        manifest_text = build_manifest(
            [
                {
                    "id": "/research",
                    "tier": "core",
                    "requires": ["research-before-spec"],
                    "next_steps": ["/research"],
                }
            ],
            contract_lines=["contracts:", "  []"],
        )
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            manifest_path = repo_root / "manifest.yaml"
            manifest_path.write_text(manifest_text, encoding="utf-8")

            with self.assertRaisesRegex(CommandSurfaceLoadError, "requires unknown contract"):
                load_command_catalog(repo_root, manifest_path)


if __name__ == "__main__":
    unittest.main()
