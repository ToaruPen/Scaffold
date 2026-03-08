from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import NamedTuple

__all__ = [
    "KNOWN_MAPPINGS",
    "MappingResult",
    "find_mappable_files",
]


class MappingResult(NamedTuple):
    old_path: str
    new_path: str
    action: str


# Consumers may have pre-Scaffold scripts in similar locations.
# Keys: fnmatch patterns relative to target repo root.
# Values: destination prefixes under the framework/ tree.
KNOWN_MAPPINGS: dict[str, str] = {
    "scripts/gates/*": "framework/scripts/gates/",
    "scripts/lib/*": "framework/scripts/lib/",
    "scripts/ci/*": "framework/scripts/ci/",
    "scripts/hooks/*": "framework/scripts/hooks/",
    "scripts/lint/*": "framework/scripts/lint/",
    ".scaffold/config/*": "framework/config/",
    ".scaffold/docs/*": "framework/docs/",
    "docs/contract/*": "framework/docs/contract/",
    "AGENTS.md": "framework/AGENTS.md",
    ".agent/*": "framework/.agent/",
    ".claude/*": "framework/.claude/",
    ".opencode/commands/*": "framework/.opencode/commands/",
    ".github/workflows/quality.yml": "framework/.github/workflows/quality.yml",
}

_MIGRATE_PATTERNS: frozenset[str] = frozenset(
    {
        "scripts/gates/*",
        "scripts/lib/*",
        "scripts/ci/*",
        "scripts/hooks/*",
        "scripts/lint/*",
    }
)

_REVIEW_PATTERNS: frozenset[str] = frozenset(
    {
        ".scaffold/config/*",
        ".scaffold/docs/*",
        "docs/contract/*",
        "AGENTS.md",
        ".agent/*",
        ".claude/*",
        ".opencode/commands/*",
    }
)


def _resolve_action(pattern: str) -> str:
    if pattern in _MIGRATE_PATTERNS:
        return "migrate"
    if pattern in _REVIEW_PATTERNS:
        return "review"
    return "manual"


def _resolve_new_path(pattern: str, framework_prefix: str, relative: str) -> str:
    if framework_prefix.endswith("/"):
        filename = Path(relative).name
        return framework_prefix + filename
    return framework_prefix


def find_mappable_files(target_path: Path) -> list[MappingResult]:
    """Walk target directory and match files against KNOWN_MAPPINGS.

    First match wins when a file matches multiple patterns.
    """
    results: list[MappingResult] = []
    root = target_path.resolve()

    if not root.is_dir():
        return results

    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            full = Path(dirpath) / filename
            relative_posix = full.relative_to(root).as_posix()

            for pattern, framework_prefix in KNOWN_MAPPINGS.items():
                if fnmatch.fnmatch(relative_posix, pattern):
                    new_path = _resolve_new_path(pattern, framework_prefix, relative_posix)
                    action = _resolve_action(pattern)
                    results.append(
                        MappingResult(
                            old_path=relative_posix,
                            new_path=new_path,
                            action=action,
                        )
                    )
                    break

    results.sort(key=lambda r: r.old_path)
    return results
