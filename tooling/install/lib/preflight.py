"""Preflight checks for validating target repositories before Scaffold installation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import NamedTuple

__all__ = [
    "PrecheckResult",
    "check_clean_working_tree",
    "check_is_git_repo",
    "check_no_existing_scaffold",
    "run_all_checks",
]


class PrecheckResult(NamedTuple):
    """Named tuple with results for one preflight check."""

    check_name: str
    passed: bool
    message: str


def check_is_git_repo(target_path: Path) -> PrecheckResult:
    """Verify the target path is inside a valid git work tree."""
    check_name = "is_git_repo"

    resolved = target_path.resolve()
    if not resolved.is_dir():
        return PrecheckResult(
            check_name=check_name,
            passed=False,
            message=f"Target path does not exist or is not a directory: {resolved}",
        )

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            check=False,
            cwd=resolved,
        )
    except FileNotFoundError:
        return PrecheckResult(
            check_name=check_name,
            passed=False,
            message="git executable not found on PATH",
        )

    if result.returncode != 0:
        return PrecheckResult(
            check_name=check_name,
            passed=False,
            message=f"Not a git repository: {resolved}",
        )

    return PrecheckResult(
        check_name=check_name,
        passed=True,
        message=f"Git repository confirmed: {resolved}",
    )


def check_no_existing_scaffold(target_path: Path) -> PrecheckResult:
    """Ensure no existing Scaffold directories already exist."""
    check_name = "no_existing_scaffold"

    resolved = target_path.resolve()
    scaffold_dir = resolved / ".scaffold"
    framework_dir = resolved / "framework"

    conflicts: list[str] = []
    if scaffold_dir.exists():
        conflicts.append(str(scaffold_dir))
    if framework_dir.exists():
        conflicts.append(str(framework_dir))

    if conflicts:
        listing = ", ".join(conflicts)
        return PrecheckResult(
            check_name=check_name,
            passed=False,
            message=f"Existing Scaffold paths found: {listing}",
        )

    return PrecheckResult(
        check_name=check_name,
        passed=True,
        message="No existing Scaffold directories detected",
    )


def check_clean_working_tree(target_path: Path) -> PrecheckResult:
    """Verify the target repo has a clean git working tree."""
    check_name = "clean_working_tree"

    resolved = target_path.resolve()
    if not resolved.is_dir():
        return PrecheckResult(
            check_name=check_name,
            passed=False,
            message=f"Target path does not exist or is not a directory: {resolved}",
        )

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
            cwd=resolved,
        )
    except FileNotFoundError:
        return PrecheckResult(
            check_name=check_name,
            passed=False,
            message="git executable not found on PATH",
        )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        return PrecheckResult(
            check_name=check_name,
            passed=False,
            message=f"Unable to determine working tree status: {stderr}",
        )

    if result.stdout.strip():
        return PrecheckResult(
            check_name=check_name,
            passed=False,
            message="Working tree has uncommitted changes",
        )

    return PrecheckResult(
        check_name=check_name,
        passed=True,
        message="Working tree is clean",
    )


def run_all_checks(target_path: Path) -> list[PrecheckResult]:
    """Run all preflight checks and return ordered results."""
    return [
        check_is_git_repo(target_path),
        check_no_existing_scaffold(target_path),
        check_clean_working_tree(target_path),
    ]
