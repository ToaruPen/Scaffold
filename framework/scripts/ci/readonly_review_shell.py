#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from framework.scripts.lib.ci_helpers import run_command  # noqa: E402

_SAFE_GIT_REF = re.compile(r"^[A-Za-z0-9._/@+-]+$")
_ACTION_WITH_BASE_REF_ARGC = 2
_NO_REF_ACTIONS = {
    "git-status": ["git", "status", "--short", "--branch"],
    "git-show-head": ["git", "show", "--stat", "--patch", "HEAD"],
    "git-rev-parse-head": ["git", "rev-parse", "HEAD"],
    "git-branch-current": ["git", "branch", "--show-current"],
    "git-remote-origin": ["git", "remote", "get-url", "origin"],
}
_BASE_REF_ACTIONS = {
    "git-diff",
    "git-log",
    "git-changed-files",
    "git-rev-parse-base",
    "git-merge-base",
}


def _build_base_ref_command(action: str, base_ref: str) -> list[str]:
    commands = {
        "git-diff": ["git", "diff", "--stat", "--patch", "--unified=5", f"{base_ref}...HEAD"],
        "git-log": ["git", "log", "--oneline", f"{base_ref}..HEAD"],
        "git-changed-files": ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        "git-rev-parse-base": ["git", "rev-parse", base_ref],
        "git-merge-base": ["git", "merge-base", "HEAD", base_ref],
    }
    command = commands.get(action)
    if command is None:
        raise ValueError("unsupported action")
    return command


def _require_git_ref(value: str) -> str:
    if not value or value.startswith("-") or not _SAFE_GIT_REF.fullmatch(value):
        raise ValueError("invalid git ref")
    return value


def _command_for_action(argv: list[str]) -> list[str]:
    if not argv:
        raise ValueError("missing action")

    action = argv[0]
    direct_command = _NO_REF_ACTIONS.get(action)
    if direct_command is not None:
        if len(argv) != 1:
            raise ValueError("unexpected arguments")
        return direct_command

    if action not in _BASE_REF_ACTIONS:
        raise ValueError("unsupported action")

    if len(argv) != _ACTION_WITH_BASE_REF_ARGC:
        raise ValueError("unexpected arguments")

    base_ref = _require_git_ref(argv[1])
    return _build_base_ref_command(action, base_ref)


def main() -> int:
    try:
        command = _command_for_action(sys.argv[1:])
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    result = run_command(command, cwd=Path.cwd(), timeout_sec=60)
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
