"""Detect file conflicts between a target repository and the Scaffold framework tree."""

from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

__all__ = [
    "ConflictResult",
    "detect_conflicts",
]


class ConflictResult(NamedTuple):
    """Represent one detected conflict during migration checks."""

    path: str
    conflict_type: str
    description: str


_SCRIPT_PREFIXES: tuple[str, ...] = (
    "scripts/gates/",
    "scripts/ci/",
    "scripts/lib/",
    "scripts/hooks/",
    "scripts/lint/",
)

_CONFIG_PREFIXES: tuple[str, ...] = ("config/",)


def _collect_relative_paths(base: Path) -> set[str]:
    """Collect all file paths under a directory as relative POSIX paths."""
    paths: set[str] = set()
    if not base.is_dir():
        return paths
    for dirpath, _dirnames, filenames in os.walk(base):
        for filename in filenames:
            full = Path(dirpath) / filename
            paths.add(full.relative_to(base).as_posix())
    return paths


def _is_script_path(relative: str) -> bool:
    """Return True when path is under a managed scripts directory."""
    return any(relative.startswith(p) for p in _SCRIPT_PREFIXES)


def _is_config_path(relative: str) -> bool:
    """Return True when path is under a managed config directory."""
    return any(relative.startswith(p) for p in _CONFIG_PREFIXES)


def _classify_overlap(relative: str) -> tuple[str, str]:
    """Classify an exact file overlap between target and framework."""
    if _is_script_path(relative):
        return (
            "script_collision",
            f"Target has script at same path as framework: {relative}",
        )
    if _is_config_path(relative):
        return (
            "config_override",
            f"Target config would be overridden by framework: {relative}",
        )
    return (
        "file_exists",
        f"Target already has file at framework path: {relative}",
    )


def _classify_managed_dir(relative: str) -> tuple[str, str] | None:
    """Classify files that sit inside framework-managed directories."""
    if _is_script_path(relative):
        return (
            "script_collision",
            f"Target script in framework-managed directory: {relative}",
        )
    if _is_config_path(relative):
        return (
            "config_override",
            f"Target config in framework-managed directory: {relative}",
        )
    return None


def detect_conflicts(
    target_path: Path,
    framework_path: Path,
) -> list[ConflictResult]:
    """Compare target_path against framework_path and return conflicts.

    Checks exact file overlaps and target files in framework-managed
    directories (scripts/, config/).
    """
    results: list[ConflictResult] = []
    framework_files = _collect_relative_paths(framework_path)
    target_files = _collect_relative_paths(target_path)

    exact_overlaps = framework_files & target_files
    for relative in sorted(exact_overlaps):
        conflict_type, description = _classify_overlap(relative)
        results.append(
            ConflictResult(
                path=relative,
                conflict_type=conflict_type,
                description=description,
            )
        )

    for relative in sorted(target_files - exact_overlaps):
        classification = _classify_managed_dir(relative)
        if classification is not None:
            conflict_type, description = classification
            results.append(
                ConflictResult(
                    path=relative,
                    conflict_type=conflict_type,
                    description=description,
                )
            )

    return results
