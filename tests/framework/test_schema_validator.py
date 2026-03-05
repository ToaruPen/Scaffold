from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from framework.scripts.lib.schema_validator import validate_schema_file


class SchemaValidatorTests(unittest.TestCase):
    def test_validate_schema_file_runs_check_jsonschema(self) -> None:
        recorded: list[dict[str, object]] = []

        def _runner(
            command: list[str],
            *,
            cwd: Path,
            timeout_sec: int,
            stdin_text: str | None = None,
        ) -> subprocess.CompletedProcess[str]:
            recorded.append(
                {
                    "command": command,
                    "cwd": cwd,
                    "timeout_sec": timeout_sec,
                    "stdin_text": stdin_text,
                }
            )
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
                {
                    "command": [
                        "check-jsonschema",
                        "--schemafile",
                        str(Path(tmp) / "schema.json"),
                        str(Path(tmp) / "target.json"),
                    ],
                    "cwd": Path(tmp),
                    "timeout_sec": 60,
                    "stdin_text": None,
                }
            ],
        )

    def test_validate_schema_file_raises_on_failure(self) -> None:
        recorded: list[dict[str, object]] = []

        def _runner(
            command: list[str],
            *,
            cwd: Path,
            timeout_sec: int,
            stdin_text: str | None = None,
        ) -> subprocess.CompletedProcess[str]:
            recorded.append(
                {
                    "command": command,
                    "cwd": cwd,
                    "timeout_sec": timeout_sec,
                    "stdin_text": stdin_text,
                }
            )
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
            self.assertEqual(recorded[0]["cwd"], repo_root)
            self.assertEqual(recorded[0]["timeout_sec"], 60)
            self.assertIsNone(recorded[0]["stdin_text"])


if __name__ == "__main__":
    unittest.main()
