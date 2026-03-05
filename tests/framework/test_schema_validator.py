from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from framework.scripts.lib.schema_validator import validate_schema_file


class SchemaValidatorTests(unittest.TestCase):
    def test_validate_schema_file_runs_check_jsonschema(self) -> None:
        recorded: list[list[str]] = []

        def _runner(
            command: list[str],
            *,
            cwd: Path,
            timeout_sec: int,
            stdin_text: str | None = None,
        ) -> subprocess.CompletedProcess[str]:
            del cwd, timeout_sec, stdin_text
            recorded.append(command)
            return subprocess.CompletedProcess(args=command, returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            validate_schema_file(
                repo_root=repo_root,
                schema_path=repo_root / "schema.json",
                target_path=repo_root / "target.json",
                command_runner=_runner,
            )

        self.assertEqual(
            recorded,
            [
                [
                    "check-jsonschema",
                    "--schemafile",
                    str(Path(tmp) / "schema.json"),
                    str(Path(tmp) / "target.json"),
                ]
            ],
        )

    def test_validate_schema_file_raises_on_failure(self) -> None:
        def _runner(
            command: list[str],
            *,
            cwd: Path,
            timeout_sec: int,
            stdin_text: str | None = None,
        ) -> subprocess.CompletedProcess[str]:
            del cwd, timeout_sec, stdin_text
            return subprocess.CompletedProcess(
                args=command,
                returncode=2,
                stdout="schema mismatch",
                stderr="",
            )

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "schema validation failed: schema mismatch"):
                validate_schema_file(
                    repo_root=repo_root,
                    schema_path=repo_root / "schema.json",
                    target_path=repo_root / "target.json",
                    command_runner=_runner,
                )


if __name__ == "__main__":
    unittest.main()
