#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from framework.scripts.lib.exit_codes import (
    EXIT_CANNOT_EXECUTE,
    EXIT_COMMAND_NOT_FOUND,
    EXIT_SOFTWARE_ERROR,
    EXIT_TIMEOUT,
)

_ALLOWED_BINARIES = {
    "check-jsonschema",
    "check-jsonschema.exe",
    "claude",
    "codex",
    "git",
    "python3",
    Path(sys.executable).name,
}


def _stream_to_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return ""


def run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout_sec: int,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    if not command:
        raise ValueError("command must not be empty")

    binary = Path(command[0]).name
    if binary not in _ALLOWED_BINARIES:
        raise ValueError(f"disallowed command: {binary}")

    try:
        return subprocess.run(
            command,
            cwd=cwd,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout_text = _stream_to_text(exc.stdout)
        stderr_text = _stream_to_text(exc.stderr)
        timeout_message = f"command timed out after {timeout_sec}s"
        stderr_text = f"{stderr_text}\n{timeout_message}" if stderr_text else timeout_message
        return subprocess.CompletedProcess(
            args=command,
            returncode=EXIT_TIMEOUT,
            stdout=stdout_text,
            stderr=stderr_text,
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(
            args=command,
            returncode=EXIT_COMMAND_NOT_FOUND,
            stdout=_stream_to_text(getattr(exc, "stdout", None)),
            stderr=f"executable not found: {exc}",
        )
    except PermissionError as exc:
        return subprocess.CompletedProcess(
            args=command,
            returncode=EXIT_CANNOT_EXECUTE,
            stdout=_stream_to_text(getattr(exc, "stdout", None)),
            stderr=f"permission denied: {exc}",
        )
    except subprocess.SubprocessError as exc:
        return subprocess.CompletedProcess(
            args=command,
            returncode=EXIT_SOFTWARE_ERROR,
            stdout="",
            stderr=f"subprocess failure: {exc}",
        )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def relative_path(repo_root: Path, path: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = repo_root.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def run_gate(
    *,
    repo_root: Path,
    gate_script: Path,
    input_path: Path,
    output_path: Path,
    policy_path: Path | None = None,
) -> int:
    command = [
        sys.executable,
        str(gate_script),
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]
    if policy_path is not None:
        command.extend(["--policy", str(policy_path)])
    result = run_command(command, cwd=repo_root, timeout_sec=120)
    return result.returncode
