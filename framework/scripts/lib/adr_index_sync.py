from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from framework.scripts.lib.adr_markdown_helpers import (
    _extract_issue_url,
    _extract_markdown_sections,
    _extract_supersedes,
    _first_matching_section_text,
    _first_section_value,
    _first_section_with_prefix,
    _relative_path,
    _required_value,
    validate_date_format,
)

_ADR_ID_FULL_RE = re.compile(r"^ADR-\d{3,}$")


def _validate_issue_url(value: str, path: Path) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"invalid issue URL: {value} in {path}")
    if any(char.isspace() for char in value):
        raise ValueError(f"invalid issue URL: {value} in {path}")
    return value


@dataclass(frozen=True)
class AdrRecord:
    adr_id: str
    title: str
    status: str
    date: str
    file_path: str
    decision_summary: str
    issue_url: str
    supersedes: tuple[str, ...]


def load_adr_record(repo_root: Path, path: Path) -> AdrRecord:
    content = path.read_text(encoding="utf-8")
    sections = _extract_markdown_sections(content)

    adr_id = _required_value(sections, "adr id", path).upper()
    if _ADR_ID_FULL_RE.match(adr_id) is None:
        raise ValueError(f"invalid ADR ID format: {adr_id} in {path}")
    title = _required_value(sections, "title", path)
    status = _required_value(sections, "status", path).lower()
    date_value = _required_value(sections, "date", path)
    date_value = validate_date_format(date_value, str(path))
    decision_summary = _first_section_value(
        _first_matching_section_text(sections, ["decision summary", "decision"])
    )
    if decision_summary is None:
        raise ValueError(f"missing section value: decision summary in {path}")

    issue_url = _extract_issue_url(sections.get("references", ""))
    if issue_url is None:
        raise ValueError(f"missing reference value: Issue in {path}")
    issue_url = _validate_issue_url(issue_url, path)

    supersedes = _extract_supersedes(_first_section_with_prefix(sections, "supersedes"))

    return AdrRecord(
        adr_id=adr_id,
        title=title,
        status=status,
        date=date_value,
        file_path=_relative_path(repo_root, path),
        decision_summary=decision_summary,
        issue_url=issue_url,
        supersedes=tuple(supersedes),
    )


def _sort_key(record: AdrRecord) -> tuple[int, str]:
    match = re.search(r"(\d+)$", record.adr_id)
    if match is None:
        raise ValueError(f"invalid ADR ID for sorting: {record.adr_id}")
    return (int(match.group(1)), record.adr_id)


def collect_adr_records(repo_root: Path, adr_dir: Path) -> list[AdrRecord]:
    resolved_repo_root = repo_root.resolve()
    resolved_adr_dir = (adr_dir if adr_dir.is_absolute() else repo_root / adr_dir).resolve()
    try:
        resolved_adr_dir.relative_to(resolved_repo_root)
    except ValueError as exc:
        raise ValueError(
            f"ADR directory is outside repository root: {resolved_adr_dir} "
            f"(root: {resolved_repo_root})"
        ) from exc

    records: list[AdrRecord] = []
    seen_by_id: dict[str, str] = {}
    for path in sorted(resolved_adr_dir.rglob("ADR-*.md")):
        record = load_adr_record(repo_root, path)
        first_path = seen_by_id.get(record.adr_id)
        if first_path is not None:
            raise ValueError(
                f"duplicate ADR ID detected: {record.adr_id} in {first_path} and {record.file_path}"
            )
        seen_by_id[record.adr_id] = record.file_path
        records.append(record)
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
            entry["supersedes"] = list(record.supersedes)
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
