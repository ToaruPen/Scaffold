#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from framework.scripts.lib.adr_index_sync import (  # noqa: E402
    build_index_payload,
    collect_adr_records,
    render_decisions_markdown,
)
from framework.scripts.lib.exit_codes import (  # noqa: E402
    EXIT_SUCCESS,
    EXIT_VALIDATION_FAILED,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate ADR index and decisions table")
    parser.add_argument("--adr-dir", default="docs/adr")
    parser.add_argument("--index-path", default="docs/adr/index.json")
    parser.add_argument("--decisions-path", default="docs/decisions.md")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    repo_root = Path(_REPO_ROOT).resolve()

    adr_dir_arg = Path(args.adr_dir)
    index_path_arg = Path(args.index_path)
    decisions_path_arg = Path(args.decisions_path)

    adr_dir = adr_dir_arg if adr_dir_arg.is_absolute() else (repo_root / adr_dir_arg).resolve()
    index_path = (
        index_path_arg if index_path_arg.is_absolute() else (repo_root / index_path_arg).resolve()
    )
    decisions_path = (
        decisions_path_arg
        if decisions_path_arg.is_absolute()
        else (repo_root / decisions_path_arg).resolve()
    )

    try:
        records = collect_adr_records(repo_root, adr_dir)
        if not records:
            raise ValueError("no ADR files found")

        payload = build_index_payload(records)
        decisions_text = render_decisions_markdown(records)

        index_path.parent.mkdir(parents=True, exist_ok=True)
        decisions_path.parent.mkdir(parents=True, exist_ok=True)

        index_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        decisions_path.write_text(decisions_text, encoding="utf-8")
        return EXIT_SUCCESS
    except (OSError, ValueError) as exc:
        print(f"adr sync failed: {exc}", file=sys.stderr)
        return EXIT_VALIDATION_FAILED


if __name__ == "__main__":
    raise SystemExit(main())
