#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from framework.scripts.lib.gate_helpers import (
    error_dict,
    parse_gate_args,
    read_json,
    require_object,
    require_text,
    write_result,
)


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


def _resolve_adr_file_path(repo_root: Path, file_path: str) -> Path:
    path = Path(file_path)
    if path.is_absolute():
        return path
    return repo_root / path


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


def _load_adr_metadata(path: Path) -> dict[str, str] | None:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None

    sections = _extract_markdown_sections(content)
    adr_id = _first_section_value(sections.get("adr id", ""))
    title = _first_section_value(sections.get("title", ""))
    status = _first_section_value(sections.get("status", ""))
    if adr_id is None or title is None or status is None:
        return None
    return {
        "adr_id": adr_id,
        "title": title,
        "status": status.lower(),
    }


def _build_result(payload: dict[str, Any], repo_root: Path) -> tuple[dict[str, Any], bool]:
    request_id = require_text(payload, "request_id")
    scope_id = require_text(payload, "scope_id")
    run_id = require_text(payload, "run_id")
    artifact_path = require_text(payload, "artifact_path")

    adr_index = require_object(payload, "adr_index")
    entries = _require_entries(adr_index)

    mismatch_reasons: set[str] = set()
    seen: set[str] = set()
    normalized_entries: list[dict[str, str]] = []
    for index, entry in enumerate(entries):
        parent = f"adr_index.entries[{index}]"
        adr_id = require_text(entry, "adr_id", parent)
        title = require_text(entry, "title", parent)
        status = require_text(entry, "status", parent)
        file_path = require_text(entry, "file_path", parent)

        if adr_id in seen:
            mismatch_reasons.add("duplicate_adr_id")
        seen.add(adr_id)

        resolved_file_path = _resolve_adr_file_path(repo_root, file_path)
        if not resolved_file_path.is_file():
            mismatch_reasons.add("missing_adr_file")
        else:
            metadata = _load_adr_metadata(resolved_file_path)
            if metadata is None:
                mismatch_reasons.add("adr_metadata_missing")
            else:
                normalized_status = status.lower()
                if (
                    metadata["adr_id"] != adr_id
                    or metadata["title"] != title
                    or metadata["status"] != normalized_status
                ):
                    mismatch_reasons.add("adr_metadata_mismatch")

        normalized_entries.append(
            {
                "adr_id": adr_id,
                "title": title,
                "status": status,
                "file_path": file_path,
            }
        )

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


def main() -> int:
    args = parse_gate_args("Validate adr-index-consistency contract")
    output_path = Path(args.output) if args.output else None

    try:
        payload = read_json(Path(args.input))
        result, passed = _build_result(payload, Path.cwd())
        exit_code = 0 if passed else 2
    except ValueError as exc:
        result = {
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
                    "file_path": "unknown",
                }
            ],
            "entry_count": 1,
            "mismatch_reasons": ["invalid_input"],
            "errors": [error_dict("E_INPUT_INVALID", str(exc), "vcs")],
        }
        exit_code = 2

    write_result(result, output_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
