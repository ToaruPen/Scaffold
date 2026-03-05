from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_ADR_ID_RE = re.compile(r"ADR-\d+", re.IGNORECASE)


@dataclass(frozen=True)
class AdrRecord:
    adr_id: str
    title: str
    status: str
    date: str
    file_path: str
    decision_summary: str
    issue_url: str
    supersedes: list[str]


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
            normalized = match.upper()
            if normalized not in values:
                values.append(normalized)
    return values


def _relative_path(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _required_value(sections: dict[str, str], key: str, path: Path) -> str:
    value = _first_section_value(sections.get(key, ""))
    if value is None:
        raise ValueError(f"missing section value: {key} in {path}")
    return value


def load_adr_record(repo_root: Path, path: Path) -> AdrRecord:
    content = path.read_text(encoding="utf-8")
    sections = _extract_markdown_sections(content)

    adr_id = _required_value(sections, "adr id", path).upper()
    title = _required_value(sections, "title", path)
    status = _required_value(sections, "status", path).lower()
    date = _required_value(sections, "date", path)
    decision_summary = _required_value(sections, "decision", path)

    issue_url = _extract_issue_url(sections.get("references", ""))
    if issue_url is None:
        raise ValueError(f"missing reference value: Issue in {path}")

    supersedes = _extract_supersedes(sections.get("supersedes", ""))

    return AdrRecord(
        adr_id=adr_id,
        title=title,
        status=status,
        date=date,
        file_path=_relative_path(repo_root, path),
        decision_summary=decision_summary,
        issue_url=issue_url,
        supersedes=supersedes,
    )


def _sort_key(record: AdrRecord) -> tuple[int, str]:
    match = re.search(r"(\d+)$", record.adr_id)
    if match is None:
        return (10**9, record.adr_id)
    return (int(match.group(1)), record.adr_id)


def collect_adr_records(repo_root: Path, adr_dir: Path) -> list[AdrRecord]:
    resolved_adr_dir = adr_dir if adr_dir.is_absolute() else repo_root / adr_dir
    records: list[AdrRecord] = []
    for path in sorted(resolved_adr_dir.rglob("ADR-*.md")):
        records.append(load_adr_record(repo_root, path))
    records.sort(key=_sort_key)
    return records


def build_index_payload(records: list[AdrRecord]) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    for record in records:
        entry: dict[str, object] = {
            "adr_id": record.adr_id,
            "title": record.title,
            "status": record.status,
            "date": record.date,
            "file_path": record.file_path,
            "decision_summary": record.decision_summary,
            "issue_url": record.issue_url,
        }
        if record.supersedes:
            entry["supersedes"] = record.supersedes
        entries.append(entry)
    return {"entries": entries}


def _table_cell(text: str) -> str:
    normalized = " ".join(text.strip().split())
    return normalized.replace("|", "/")


def render_decisions_markdown(records: list[AdrRecord]) -> str:
    lines = [
        "# Decisions Index",
        "",
        "Generated from ADR files. Do not edit manually.",
        "",
        "## Decision Index",
        "",
        "| ADR ID | Title | Decision Summary | Issue | ADR Path |",
        "| --- | --- | --- | --- | --- |",
    ]
    for record in records:
        lines.append(
            "| "
            + " | ".join(
                [
                    _table_cell(record.adr_id),
                    _table_cell(record.title),
                    _table_cell(record.decision_summary),
                    _table_cell(record.issue_url),
                    _table_cell(record.file_path),
                ]
            )
            + " |"
        )
    lines.append("")
    return "\n".join(lines)
