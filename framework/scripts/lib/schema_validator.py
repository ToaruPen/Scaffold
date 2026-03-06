from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Protocol

from framework.scripts.lib import ci_helpers
from framework.scripts.lib.exit_codes import EXIT_SUCCESS


class SchemaCommandRunner(Protocol):
    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        timeout_sec: int,
        stdin_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]: ...


def validate_schema_file(
    *,
    repo_root: Path,
    schema_path: Path,
    target_path: Path,
    timeout_sec: int = 60,
    command_runner: SchemaCommandRunner = ci_helpers.run_command,
) -> None:
    executable = shutil.which("check-jsonschema")
    if executable is None:
        local_executable = repo_root / ".venv/bin/check-jsonschema"
        executable = str(local_executable) if local_executable.exists() else "check-jsonschema"
    result = command_runner(
        [executable, "--schemafile", str(schema_path), str(target_path)],
        cwd=repo_root,
        timeout_sec=timeout_sec,
    )
    if result.returncode != EXIT_SUCCESS:
        message = result.stderr.strip() or result.stdout.strip()
        raise ValueError(f"schema validation failed: {message}")
