#!/usr/bin/env python3
"""CLI entry point for the Scaffold install helper.

Validates target repositories via preflight checks, displays an installation
plan, and optionally executes ``git subtree add`` to bootstrap Scaffold.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tooling.install.lib.preflight import PrecheckResult, run_all_checks  # noqa: E402, RUF100

__all__: list[str] = []


def _print_plan(
    target_repo: Path,
    scaffold_repo: Path,
    prefix: str,
    framework_items: list[str],
) -> None:
    """Print the installation plan details to stdout."""
    print("Installation plan")
    print(f"  Target repo   : {target_repo}")
    print(f"  Scaffold repo : {scaffold_repo}")
    print(f"  Subtree prefix: {prefix}")
    print()
    print("Contents to sync (framework/):")
    if framework_items:
        for item in framework_items:
            print(f"  {item}")
    else:
        print("  (no items found under framework/)")


def _list_framework_contents(scaffold_repo: Path) -> list[str]:
    """Return top-level files and directories under framework."""
    framework_dir = scaffold_repo / "framework"
    if not framework_dir.is_dir():
        return []
    entries: list[str] = []
    for child in sorted(framework_dir.iterdir()):
        suffix = "/" if child.is_dir() else ""
        entries.append(f"{child.name}{suffix}")
    return entries


def _print_failures(results: list[PrecheckResult]) -> None:
    """Print failed preflight check results to stderr."""
    for result in results:
        if not result.passed:
            print(f"FAIL  {result.check_name}: {result.message}", file=sys.stderr)


def _run_subtree_add(
    target_repo: Path,
    scaffold_repo: Path,
    prefix: str,
) -> int:
    """Run ``git subtree add`` and return the subprocess exit status."""
    remote = str(scaffold_repo.resolve())
    cmd = [
        "git",
        "subtree",
        "add",
        f"--prefix={prefix}",
        remote,
        "framework-dist",
        "--squash",
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False, cwd=target_repo, capture_output=True, text=True)
    if result.returncode != 0 and result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments for install_helper."""
    parser = argparse.ArgumentParser(
        description="Bootstrap Scaffold into a target repository via git subtree",
    )
    parser.add_argument(
        "--target-repo",
        required=True,
        type=Path,
        help="Path to the target repository",
    )
    parser.add_argument(
        "--scaffold-repo",
        type=Path,
        default=Path.cwd(),
        help="Path to the Scaffold repository (default: current directory)",
    )
    parser.add_argument(
        "--prefix",
        default=".scaffold",
        help="Subtree prefix in the target repo (default: .scaffold)",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the installation plan without executing",
    )
    mode_group.add_argument(
        "--execute",
        action="store_true",
        help="Execute the git subtree add operation",
    )
    return parser.parse_args()


def main() -> int:
    """Run install_helper CLI flow and return an exit code."""
    args = _parse_args()

    target_repo: Path = args.target_repo.resolve()
    scaffold_repo: Path = args.scaffold_repo.resolve()
    prefix: str = args.prefix

    if not target_repo.is_dir():
        print(f"error: target repo does not exist: {target_repo}", file=sys.stderr)
        return 2
    if not scaffold_repo.is_dir():
        print(f"error: scaffold repo does not exist: {scaffold_repo}", file=sys.stderr)
        return 2

    results = run_all_checks(target_repo)
    failures = [r for r in results if not r.passed]
    if failures:
        print("Preflight checks failed:", file=sys.stderr)
        _print_failures(results)
        return 2

    print("All preflight checks passed.")
    print()

    framework_items = _list_framework_contents(scaffold_repo)
    _print_plan(target_repo, scaffold_repo, prefix, framework_items)
    print()

    if args.dry_run or not args.execute:
        if args.dry_run:
            print("Dry run complete. No changes made.")
        else:
            print("To proceed, add --execute to run the installation.")
        return 0

    rc = _run_subtree_add(target_repo, scaffold_repo, prefix)
    if rc != 0:
        print(f"error: git subtree add failed (exit {rc})", file=sys.stderr)
        return rc

    print("Installation complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
