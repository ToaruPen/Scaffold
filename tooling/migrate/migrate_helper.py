#!/usr/bin/env python3
"""Scaffold migration helper — analyze a target repo and generate a migration report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tooling.migrate.lib.conflict_detector import detect_conflicts  # noqa: E402, RUF100
from tooling.migrate.lib.path_mapper import find_mappable_files  # noqa: E402, RUF100
from tooling.migrate.lib.report_formatter import format_report  # noqa: E402, RUF100


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for migration helper execution."""
    parser = argparse.ArgumentParser(
        description=(
            "Analyze a target repository for Scaffold migration readiness. "
            "Scans for mappable files, detects conflicts with the framework "
            "tree, and generates a migration report."
        ),
    )
    parser.add_argument(
        "--target-repo",
        required=True,
        help="path to the target repository to analyze (read-only)",
    )
    parser.add_argument(
        "--scaffold-repo",
        default=None,
        help="path to the Scaffold repository (default: current working directory)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="write report to file instead of stdout",
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=["text"],
        dest="report_format",
        help="output format (default: text)",
    )
    return parser.parse_args()


def _validate_target_repo(target: Path) -> str | None:
    """Validate the target repository path.

    Args:
        target: Path provided by --target-repo.

    Returns:
        Error message when invalid, otherwise None.
    """
    if not target.exists():
        return f"target repo does not exist: {target}"
    if not target.is_dir():
        return f"target repo is not a directory: {target}"
    return None


def _resolve_scaffold_repo(raw: str | None) -> Path:
    """Resolve scaffold repository root from CLI input.

    Args:
        raw: Optional --scaffold-repo argument.

    Returns:
        Explicit scaffold path or cwd when not provided.
    """
    if raw is not None:
        return Path(raw).resolve()
    return Path.cwd()


def _validate_scaffold_repo(scaffold: Path) -> str | None:
    """Validate scaffold repo has framework/ directory required for migration."""
    framework = scaffold / "framework"
    if not framework.is_dir():
        return f"scaffold repo missing framework/ directory: {scaffold}"
    return None


def _write_output(report: str, output_path: Path | None) -> None:
    """Write report text to output destination.

    Args:
        report: Rendered migration report.
        output_path: Optional file path; stdout when None.
    """
    if output_path is None:
        sys.stdout.write(report)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")


def main() -> int:
    """Run migration helper flow and return CLI exit status."""
    args = _parse_args()

    target_path = Path(args.target_repo).resolve()
    error = _validate_target_repo(target_path)
    if error is not None:
        print(f"error: {error}", file=sys.stderr)
        return 2

    scaffold_path = _resolve_scaffold_repo(args.scaffold_repo)
    error = _validate_scaffold_repo(scaffold_path)
    if error is not None:
        print(f"error: {error}", file=sys.stderr)
        return 2

    framework_path = scaffold_path / "framework"
    output_path = Path(args.output) if args.output is not None else None

    try:
        mappings = find_mappable_files(target_path)
        conflicts = detect_conflicts(target_path, framework_path)
        report = format_report(mappings, conflicts)
        _write_output(report, output_path)
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if output_path is not None:
        print(f"Report written to {output_path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
