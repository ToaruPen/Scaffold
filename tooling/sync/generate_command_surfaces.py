#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tooling.sync.lib.command_surface_loader import (  # noqa: E402
    CommandSurfaceLoadError,
    load_command_catalog,
)

_AGENTS = ("codex", "claude", "opencode")


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
    manifest_path: str,
    tiers: dict[str, list[str]],
    include_conditional: bool,
) -> dict[str, object]:
    core = list(tiers["core"])
    conditional = list(tiers["conditional"])
    commands = core + (conditional if include_conditional else [])
    return {
        "agent": agent,
        "source_manifest": manifest_path,
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
    runtime_root = Path.cwd()
    output_root = (
        Path(args.output_root)
        if args.output_root is not None
        else _default_output_root(include_conditional=args.enable_conditional)
    )

    try:
        catalog = load_command_catalog(
            runtime_root,
            args.manifest,
            require_metadata=False,
            require_contracts=False,
        )
        output_root.mkdir(parents=True, exist_ok=True)
        for agent in _target_agents(args.agent):
            payload = _build_surface(
                agent=agent,
                manifest_path=catalog["manifest_path"],
                tiers=catalog["tiers"],
                include_conditional=args.enable_conditional,
            )
            output_path = output_root / f"{agent}.commands.json"
            output_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
            )
            print(output_path)
        return 0
    except (CommandSurfaceLoadError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
