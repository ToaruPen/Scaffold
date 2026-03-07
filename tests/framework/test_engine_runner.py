from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from framework.scripts.lib.engine_runner import (
    _CLAUDE_BUILTIN_TOOLS,
    _CLAUDE_READONLY_REVIEW_SHELL,
    _build_claude_allowed_tools,
    _claude_prompt_addendum,
    _run_engine,
)
from framework.scripts.lib.paths_metadata import RunnerConfig


def _config(engine: str) -> RunnerConfig:
    return RunnerConfig(
        engine=engine,
        scope_id="issue-1",
        run_id="run-1",
        base_ref="main",
        results_dir=Path(".scaffold/review_results"),
        prompt_template=Path("framework/config/review-engine-prompt.json"),
        canonical_schema=Path("schema.json"),
        codex_schema=Path("schema.json"),
        policy_path=Path("framework/config/review-evidence-policy.yaml"),
        timeout_sec=60,
        codex_model=None,
        claude_model=None,
        codex_reasoning_effort=None,
        claude_effort=None,
        declared_targets_file=None,
        adr_index_file=None,
    )


class EngineRunnerTests(unittest.TestCase):
    def test_run_engine_rejects_unsupported_engine(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            with self.assertRaisesRegex(ValueError, "unsupported engine: invalid"):
                _run_engine(
                    config=_config("invalid"),
                    repo_root=repo_root,
                    prompt_text="prompt",
                    raw_output_path=repo_root / "raw-output.txt",
                )

    def test_run_engine_resolves_relative_schema_paths_against_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            schema_path = repo_root / "schema.json"
            schema_path.write_text('{"type":"object"}', encoding="utf-8")

            with patch("framework.scripts.lib.engine_runner._ci_run_command") as run_command:
                run_command.return_value = subprocess.CompletedProcess(
                    args=["claude"], returncode=0, stdout="{}", stderr=""
                )
                result = _run_engine(
                    config=_config("claude"),
                    repo_root=repo_root,
                    prompt_text="prompt",
                    raw_output_path=repo_root / "raw-output.txt",
                )

        self.assertEqual(result, "{}")
        run_command.assert_called_once()

    def test_run_engine_uses_restricted_claude_tool_profile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            schema_path = repo_root / "schema.json"
            schema_path.write_text('{"type":"object"}', encoding="utf-8")
            config = _config("claude")
            config = RunnerConfig(
                **{
                    **config.__dict__,
                    "claude_model": "opus",
                    "claude_effort": "high",
                }
            )

            with patch("framework.scripts.lib.engine_runner._ci_run_command") as run_command:
                run_command.return_value = subprocess.CompletedProcess(
                    args=["claude"], returncode=0, stdout="{}", stderr=""
                )
                _run_engine(
                    config=config,
                    repo_root=repo_root,
                    prompt_text="prompt",
                    raw_output_path=repo_root / "raw-output.txt",
                )

        command = run_command.call_args.args[0]
        self.assertIn("--permission-mode", command)
        self.assertIn("dontAsk", command)
        self.assertIn("--model", command)
        self.assertIn("opus", command)
        self.assertIn("--effort", command)
        self.assertIn("high", command)
        self.assertIn("--tools", command)
        self.assertIn(",".join(_CLAUDE_BUILTIN_TOOLS), command)
        self.assertIn("--allowedTools", command)
        for tool in _build_claude_allowed_tools("main"):
            self.assertIn(tool, command)
        self.assertIn(
            f"{_CLAUDE_READONLY_REVIEW_SHELL} git-diff main",
            command[-1],
        )

    def test_build_claude_allowed_tools_uses_exact_readonly_commands(self) -> None:
        tools = _build_claude_allowed_tools("origin/main")

        self.assertNotIn(":*", "\n".join(tools))
        self.assertIn(
            f"Bash({_CLAUDE_READONLY_REVIEW_SHELL} git-diff origin/main)",
            tools,
        )
        self.assertIn(
            f"Bash({_CLAUDE_READONLY_REVIEW_SHELL} git-show-head)",
            tools,
        )

    def test_build_claude_allowed_tools_quotes_valid_shell_metachar_refs(self) -> None:
        tools = _build_claude_allowed_tools("feature$(echo)")

        self.assertIn(
            f"Bash({_CLAUDE_READONLY_REVIEW_SHELL} git-diff 'feature$(echo)')",
            tools,
        )

    def test_build_claude_allowed_tools_rejects_invalid_base_ref(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid git ref"):
            _build_claude_allowed_tools("main --bad")

    def test_claude_prompt_addendum_rejects_invalid_base_ref(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid git ref"):
            _claude_prompt_addendum("main --bad")


if __name__ == "__main__":
    unittest.main()
