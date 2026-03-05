#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from framework.scripts.lib.adr_markdown_helpers import (
    _extract_issue_url,
    _extract_markdown_sections,
    _extract_supersedes,
    _first_matching_section_text,
    _first_section_value,
    _first_section_with_prefix,
    _normalize_adr_id,
    validate_date_format,
)
from framework.scripts.lib.exit_codes import EXIT_SUCCESS, EXIT_VALIDATION_FAILED
from framework.scripts.lib.gate_helpers import (
    error_dict,
    parse_gate_args,
    read_json,
    require_object,
    require_text,
    write_result,
)

_DECISIONS_HEADER = ["ADR ID", "Title", "Decision Summary", "Issue", "ADR Path"]
_DECISIONS_COLS = len(_DECISIONS_HEADER)
_ADR_ID_FULL_RE = re.compile(r"^ADR-\d{3,}$")


def _optional_list_of_texts(obj: dict[str, Any], key: str, parent: str = "") -> list[str] | None:
    raw = obj.get(key)
    if raw is None:
        return None
    prefix = f"{parent}." if parent else ""
    if not isinstance(raw, list):
        raise ValueError(f"invalid list: {prefix}{key}")

    values: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"invalid string element: {prefix}{key}")
        values.append(item.strip())
    return values


def _require_entries(adr_index: dict[str, Any]) -> list[dict[str, Any]]:
    raw = adr_index.get("entries")
    if not isinstance(raw, list) or not raw:
        raise ValueError("missing or invalid non-empty list: adr_index.entries")

    values: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("invalid object element: adr_index.entries")
        values.append(item)
    return values


def _resolve_adr_file_path(repo_root: Path, file_path: str) -> Path | None:
    path = Path(file_path)
    candidate = path if path.is_absolute() else repo_root / path
    resolved_repo_root = repo_root.resolve()
    resolved_candidate = candidate.resolve()
    try:
        resolved_candidate.relative_to(resolved_repo_root)
    except ValueError:
        return None
    return resolved_candidate


def _validate_adr_id_format(value: str, parent: str) -> str:
    if _ADR_ID_FULL_RE.match(value) is None:
        raise ValueError(f"invalid ADR ID format: {parent}: {value}")
    return value


def _validate_issue_url_format(value: str, parent: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"invalid issue_url format: {parent}: {value}")
    if any(char.isspace() for char in value):
        raise ValueError(f"invalid issue_url format: {parent}: {value}")
    return value


def _load_adr_metadata(path: Path) -> dict[str, Any] | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    sections = _extract_markdown_sections(content)
    adr_id = _first_section_value(sections.get("adr id", ""))
    title = _first_section_value(sections.get("title", ""))
    status = _first_section_value(sections.get("status", ""))
    date = _first_section_value(sections.get("date", ""))
    decision_summary = _first_section_value(
        _first_matching_section_text(sections, ["decision summary", "decision"])
    )
    issue_url = _extract_issue_url(sections.get("references", ""))
    try:
        supersedes = _extract_supersedes(_first_section_with_prefix(sections, "supersedes"))
    except ValueError:
        return None
    if (
        adr_id is None
        or title is None
        or status is None
        or date is None
        or decision_summary is None
        or issue_url is None
    ):
        return None

    try:
        normalized_date = validate_date_format(date, f"adr body {path}")
        normalized_issue_url = _validate_issue_url_format(issue_url, f"adr body {path}")
    except ValueError:
        return None

    try:
        normalized_adr_id = _validate_adr_id_format(_normalize_adr_id(adr_id), f"adr body {path}")
    except ValueError:
        return None

    return {
        "adr_id": normalized_adr_id,
        "title": title,
        "status": status.lower(),
        "date": normalized_date,
        "decision_summary": decision_summary,
        "issue_url": normalized_issue_url,
        "supersedes": supersedes,
    }


def _parse_table_row(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return None
    return [part.strip() for part in stripped[1:-1].split("|")]


def _normalize_decisions_cell(value: str) -> str:
    return " ".join(value.strip().split()).replace("|", "/")


def _find_decisions_header(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if _parse_table_row(line) == _DECISIONS_HEADER:
            return index
    return None


def _parse_decisions_rows(
    lines: list[str], start: int
) -> tuple[dict[str, dict[str, str]] | None, str | None]:
    values: dict[str, dict[str, str]] = {}
    parsed_table_rows = False
    for line in lines[start:]:
        row = _parse_table_row(line)
        if row is None:
            if parsed_table_rows:
                break
            continue
        parsed_table_rows = True
        if len(row) != _DECISIONS_COLS:
            return None, "decisions_index_invalid"

        adr_id, title, decision_summary, issue_url, file_path = row
        if not adr_id:
            continue
        normalized_adr_id = _normalize_adr_id(adr_id)
        if normalized_adr_id in values:
            return None, "decisions_index_duplicate_adr_id"
        values[normalized_adr_id] = {
            "title": title,
            "decision_summary": decision_summary,
            "issue_url": issue_url,
            "file_path": file_path,
        }
    return values, None


def _load_decisions_index(path: Path) -> tuple[dict[str, dict[str, str]] | None, str | None]:
    if not path.is_file():
        return None, "decisions_index_missing"

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None, "decisions_index_unreadable"

    header_index = _find_decisions_header(lines)
    if header_index is None:
        return None, "decisions_index_invalid"

    separator_index = header_index + 1
    if separator_index >= len(lines):
        return None, "decisions_index_invalid"

    separator_row = _parse_table_row(lines[separator_index])
    if separator_row is None or len(separator_row) != _DECISIONS_COLS:
        return None, "decisions_index_invalid"

    return _parse_decisions_rows(lines, separator_index + 1)


def _parse_index_entry(entry: dict[str, Any], parent: str) -> dict[str, Any]:
    normalized_adr_id = _validate_adr_id_format(
        _normalize_adr_id(require_text(entry, "adr_id", parent)),
        f"{parent}.adr_id",
    )
    parsed: dict[str, Any] = {
        "adr_id": normalized_adr_id,
        "title": require_text(entry, "title", parent),
        "status": require_text(entry, "status", parent),
        "date": validate_date_format(require_text(entry, "date", parent), f"{parent}.date"),
        "file_path": require_text(entry, "file_path", parent),
        "decision_summary": require_text(entry, "decision_summary", parent),
        "issue_url": _validate_issue_url_format(
            require_text(entry, "issue_url", parent),
            f"{parent}.issue_url",
        ),
    }
    supersedes = _optional_list_of_texts(entry, "supersedes", parent)
    if supersedes:
        normalized_supersedes: list[str] = []
        for index, item in enumerate(supersedes):
            normalized = _validate_adr_id_format(
                _normalize_adr_id(item),
                f"{parent}.supersedes[{index}]",
            )
            normalized_supersedes.append(normalized)
        parsed["supersedes"] = normalized_supersedes
    return parsed


def _check_body_consistency(entry: dict[str, Any], repo_root: Path) -> set[str]:
    reasons: set[str] = set()
    resolved_file_path = _resolve_adr_file_path(repo_root, entry["file_path"])
    if resolved_file_path is None:
        reasons.add("adr_file_outside_repo")
        return reasons
    if not resolved_file_path.is_file():
        reasons.add("missing_adr_file")
        return reasons

    metadata = _load_adr_metadata(resolved_file_path)
    if metadata is None:
        reasons.add("adr_metadata_missing")
        return reasons

    if (
        metadata["adr_id"] != entry["adr_id"]
        or metadata["title"] != entry["title"]
        or metadata["status"] != entry["status"].lower()
        or metadata["date"] != entry["date"]
        or metadata["decision_summary"] != entry["decision_summary"]
        or metadata["issue_url"] != entry["issue_url"]
        or metadata["supersedes"] != entry.get("supersedes", [])
    ):
        reasons.add("adr_metadata_mismatch")
    return reasons


def _check_decisions_consistency(
    entry: dict[str, Any],
    decisions_index: dict[str, dict[str, str]] | None,
    seen_decision_rows: set[str],
) -> set[str]:
    reasons: set[str] = set()
    if decisions_index is None:
        return reasons

    row = decisions_index.get(entry["adr_id"])
    if row is None:
        reasons.add("decisions_index_missing_entry")
        return reasons

    seen_decision_rows.add(entry["adr_id"])
    if (
        row["title"] != _normalize_decisions_cell(entry["title"])
        or row["decision_summary"] != _normalize_decisions_cell(entry["decision_summary"])
        or row["issue_url"] != _normalize_decisions_cell(entry["issue_url"])
        or row["file_path"] != _normalize_decisions_cell(entry["file_path"])
    ):
        reasons.add("decisions_index_mismatch")
    return reasons


def _build_result(payload: dict[str, Any], repo_root: Path) -> tuple[dict[str, Any], bool]:
    request_id = require_text(payload, "request_id")
    scope_id = require_text(payload, "scope_id")
    run_id = require_text(payload, "run_id")
    artifact_path = require_text(payload, "artifact_path")

    adr_index = require_object(payload, "adr_index")
    entries = _require_entries(adr_index)
    decisions_index, decisions_error = _load_decisions_index(repo_root / "docs" / "decisions.md")

    mismatch_reasons: set[str] = set()
    seen_ids: set[str] = set()
    seen_decision_rows: set[str] = set()
    normalized_entries: list[dict[str, Any]] = []

    if decisions_error is not None:
        mismatch_reasons.add(decisions_error)

    for index, entry in enumerate(entries):
        parent = f"adr_index.entries[{index}]"
        parsed = _parse_index_entry(entry, parent)

        adr_id = parsed["adr_id"]
        if adr_id in seen_ids:
            mismatch_reasons.add("duplicate_adr_id")
        seen_ids.add(adr_id)

        mismatch_reasons.update(_check_body_consistency(parsed, repo_root))
        mismatch_reasons.update(
            _check_decisions_consistency(parsed, decisions_index, seen_decision_rows)
        )
        normalized_entries.append(parsed)

    if decisions_index is not None and set(decisions_index.keys()) != seen_decision_rows:
        mismatch_reasons.add("decisions_index_extra_entry")

    mismatch_reason_list = sorted(mismatch_reasons)
    passed = len(mismatch_reason_list) == 0
    result: dict[str, Any] = {
        "request_id": request_id,
        "scope_id": scope_id,
        "run_id": run_id,
        "status": "pass" if passed else "fail",
        "artifact_path": artifact_path,
        "entries": normalized_entries,
        "entry_count": len(normalized_entries),
        "mismatch_reasons": mismatch_reason_list,
    }
    if not passed:
        result["errors"] = [error_dict("E_PROVIDER_FAILURE", "adr index check failed", "vcs")]
    return result, passed


def _invalid_input_result(message: str) -> dict[str, Any]:
    return {
        "request_id": "unknown",
        "scope_id": "unknown",
        "run_id": "unknown",
        "status": "fail",
        "artifact_path": "unknown",
        "entries": [
            {
                "adr_id": "unknown",
                "title": "invalid_input",
                "status": "unknown",
                "date": "1970-01-01",
                "file_path": "unknown",
                "decision_summary": "unknown",
                "issue_url": "https://example.invalid/issues/unknown",
            }
        ],
        "entry_count": 1,
        "mismatch_reasons": ["invalid_input"],
        "errors": [error_dict("E_INPUT_INVALID", message, "vcs")],
    }


def main() -> int:
    args = parse_gate_args("Validate adr-index-consistency contract")
    output_path = Path(args.output) if args.output else None

    try:
        payload = read_json(Path(args.input))
        result, passed = _build_result(payload, Path.cwd())
        exit_code = EXIT_SUCCESS if passed else EXIT_VALIDATION_FAILED
    except ValueError as exc:
        result = _invalid_input_result(str(exc))
        exit_code = EXIT_VALIDATION_FAILED

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
