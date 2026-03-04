#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

_AGENTS = ("codex", "claude", "opencode")
_ALLOWED_TIERS = {"core", "conditional"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate agent command surfaces from manifest command tiers"
    )
    parser.add_argument(
        "--manifest",
        default="framework/scripts/manifest.yaml",
        help="Path to manifest YAML (default: framework/scripts/manifest.yaml)",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help=(
            "Output directory for generated surfaces "
            "(default: tooling/sync/generated/default or .../with-conditional)"
        ),
    )
    parser.add_argument(
        "--agent",
        choices=(*_AGENTS, "all"),
        default="all",
        help="Target agent (default: all)",
    )
    parser.add_argument(
        "--enable-conditional",
        action="store_true",
        help="Include conditional tier commands in generated output",
    )
    return parser.parse_args()


def _require_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be a mapping")
    return value


def _load_manifest(manifest_path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"failed to read manifest: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"failed to parse manifest YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("manifest root must be a mapping")
    return data


def _extract_tiers(manifest: dict[str, Any]) -> tuple[list[str], list[str]]:
    must_command_contracts = _require_mapping(manifest, "must_command_contracts")
    command_tiers = _require_mapping(manifest, "command_tiers")
    command_keys_str = {str(command) for command in command_tiers}

    invalid_tiers = sorted(
        str(command)
        for command, tier in command_tiers.items()
        if not isinstance(command, str) or tier not in _ALLOWED_TIERS
    )
    if invalid_tiers:
        details = ", ".join(invalid_tiers)
        raise ValueError(f"command_tiers contains invalid entries: {details}")

    missing = sorted(
        str(command) for command in must_command_contracts if str(command) not in command_keys_str
    )
    if missing:
        details = ", ".join(missing)
        raise ValueError(f"must_command_contracts missing tier classification: {details}")

    core = sorted(command for command, tier in command_tiers.items() if tier == "core")
    conditional = sorted(
        command for command, tier in command_tiers.items() if tier == "conditional"
    )
    return core, conditional


def _target_agents(agent: str) -> tuple[str, ...]:
    if agent == "all":
        return _AGENTS
    return (agent,)


def _default_output_root(*, include_conditional: bool) -> Path:
    profile = "with-conditional" if include_conditional else "default"
    return Path("tooling/sync/generated") / profile


def _build_surface(
    *,
    agent: str,
    manifest_path: Path,
    core: list[str],
    conditional: list[str],
    include_conditional: bool,
) -> dict[str, Any]:
    commands = core + (conditional if include_conditional else [])
    return {
        "agent": agent,
        "source_manifest": str(manifest_path),
        "policy": {
            "core_always_enabled": True,
            "conditional_enabled": include_conditional,
        },
        "tiers": {
            "core": core,
            "conditional": conditional,
        },
        "commands": commands,
    }


def main() -> int:
    args = _parse_args()
    manifest_path = Path(args.manifest)
    output_root = (
        Path(args.output_root)
        if args.output_root is not None
        else _default_output_root(include_conditional=args.enable_conditional)
    )

    try:
        manifest = _load_manifest(manifest_path)
        core, conditional = _extract_tiers(manifest)

        output_root.mkdir(parents=True, exist_ok=True)
        for agent in _target_agents(args.agent):
            payload = _build_surface(
                agent=agent,
                manifest_path=manifest_path,
                core=core,
                conditional=conditional,
                include_conditional=args.enable_conditional,
            )
            output_path = output_root / f"{agent}.commands.json"
            output_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
            )
            print(output_path)
        return 0
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
