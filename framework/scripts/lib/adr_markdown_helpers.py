from __future__ import annotations

import re
from pathlib import Path

_ADR_ID_RE = re.compile(r"ADR-\d+", re.IGNORECASE)


def _normalize_adr_id(value: str) -> str:
    return value.strip().upper()


def _extract_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    current: str | None = None
    buffer: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(buffer)
            current = line[3:].strip().lower()
            buffer = []
            continue
        if current is not None:
            buffer.append(raw_line)
    if current is not None:
        sections[current] = "\n".join(buffer)
    return sections


def _first_section_value(text: str) -> str | None:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("-"):
            line = line[1:].strip()
        if line:
            return line
    return None


def _extract_issue_url(text: str) -> str | None:
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("-"):
            line = line[1:].strip()
        if not line:
            continue
        lowered = line.lower()
        if not lowered.startswith("issue:"):
            continue
        value = line.split(":", 1)[1].strip()
        if value:
            return value
    return None


def _extract_supersedes(text: str) -> list[str]:
    values: list[str] = []
    for raw_line in text.splitlines():
        matches = _ADR_ID_RE.findall(raw_line)
        for match in matches:
            normalized = _normalize_adr_id(match)
            if normalized not in values:
                values.append(normalized)
    return values


def _relative_path(repo_root: Path, path: Path) -> str:
    resolved_root = repo_root.resolve()
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError as exc:
        raise ValueError(
            f"ADR file is outside repository root: {resolved_path} (root: {resolved_root})"
        ) from exc


def _required_value(sections: dict[str, str], key: str, path: Path) -> str:
    value = _first_section_value(sections.get(key, ""))
    if value is None:
        raise ValueError(f"missing section value: {key} in {path}")
    return value


def _first_matching_section_text(sections: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        if key in sections:
            return sections[key]
    return ""


def _first_section_with_prefix(sections: dict[str, str], prefix: str) -> str:
    for key, value in sections.items():
        if key.startswith(prefix):
            return value
    return ""
