from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tooling.migrate.lib.conflict_detector import ConflictResult
    from tooling.migrate.lib.path_mapper import MappingResult

__all__ = ["format_report"]

_SEPARATOR = "=" * 60

_CONFLICT_FIX_LABELS: dict[str, str] = {
    "file_exists": "Resolve file conflict",
    "script_collision": "Resolve script collision",
    "config_override": "Merge or replace config",
}


def format_report(
    mappings: list[MappingResult],
    conflicts: list[ConflictResult],
) -> str:
    sections: list[str] = [
        _format_header(),
        _format_summary(mappings, conflicts),
        _format_mappings(mappings),
        _format_conflicts(conflicts),
        _format_manual_fixes(mappings, conflicts),
    ]
    return "\n".join(sections)


def _format_header() -> str:
    return f"{_SEPARATOR}\nScaffold Migration Analysis Report\n{_SEPARATOR}"


def _format_summary(
    mappings: list[MappingResult],
    conflicts: list[ConflictResult],
) -> str:
    manual_count = sum(1 for m in mappings if m.action in {"manual", "review"}) + len(conflicts)
    lines = [
        "",
        "## Summary",
        "",
        f"  Total mappings found:    {len(mappings)}",
        f"  Total conflicts:         {len(conflicts)}",
        f"  Required manual fixes:   {manual_count}",
        "",
    ]
    return "\n".join(lines)


def _format_mappings(mappings: list[MappingResult]) -> str:
    lines = [_SEPARATOR, "## File Mappings", ""]
    if not mappings:
        lines.append("  No mappable files found.")
        lines.append("")
        return "\n".join(lines)

    old_width = max(*(len(m.old_path) for m in mappings), len("Old Path"))
    new_width = max(*(len(m.new_path) for m in mappings), len("New Path"))

    lines.append(f"  {'Old Path':<{old_width}}  {'New Path':<{new_width}}  Action")
    lines.append(f"  {'-' * old_width}  {'-' * new_width}  ------")
    for m in mappings:
        lines.append(f"  {m.old_path:<{old_width}}  {m.new_path:<{new_width}}  {m.action}")
    lines.append("")
    return "\n".join(lines)


def _format_conflicts(conflicts: list[ConflictResult]) -> str:
    lines = [_SEPARATOR, "## Conflicts", ""]
    if not conflicts:
        lines.append("  No conflicts found.")
        lines.append("")
        return "\n".join(lines)

    for c in conflicts:
        lines.append(f"  [{c.conflict_type}] {c.path}")
        lines.append(f"    {c.description}")
        lines.append("")

    return "\n".join(lines)


def _format_manual_fixes(
    mappings: list[MappingResult],
    conflicts: list[ConflictResult],
) -> str:
    lines = [_SEPARATOR, "## Required Manual Fixes", ""]
    fix_items: list[str] = []

    for m in mappings:
        if m.action == "manual":
            fix_items.append(f"  - Move {m.old_path} -> {m.new_path} (manual adaptation required)")
        elif m.action == "review":
            fix_items.append(f"  - Review {m.old_path} -> {m.new_path} before migration")

    for c in conflicts:
        label = _CONFLICT_FIX_LABELS.get(c.conflict_type, "Resolve conflict")
        fix_items.append(f"  - {label}: {c.path}")

    if not fix_items:
        lines.append("  No manual fixes required.")
    else:
        lines.extend(fix_items)

    lines.append("")
    return "\n".join(lines)
