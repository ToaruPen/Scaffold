from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO_ROOT / "framework/scripts/ci/run_review_engine.py"
PROMPT_TEMPLATE = REPO_ROOT / "framework/config/review-engine-prompt.json"


def _load_runner_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_review_engine_module", RUNNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RunReviewEngineTests(unittest.TestCase):
    runner: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = _load_runner_module()

    def test_stream_to_text_handles_str_bytes_and_none(self) -> None:
        self.assertEqual(self.runner._stream_to_text("abc"), "abc")
        self.assertEqual(self.runner._stream_to_text(b"abc"), "abc")
        self.assertEqual(self.runner._stream_to_text(None), "")

    def test_extract_review_json_handles_result_string_envelope(self) -> None:
        payload = {
            "status": "approved",
            "summary": "ok",
            "findings": [],
        }
        envelope = {"type": "result", "result": json.dumps(payload)}
        extracted = self.runner._extract_review_json(json.dumps(envelope))
        self.assertEqual(extracted["status"], "approved")
        self.assertEqual(extracted["findings"], [])

    def test_main_creates_separated_output_and_intermediate_layout(self) -> None:
        review_payload = {
            "status": "approved",
            "summary": "looks good",
            "findings": [],
        }

        def fake_run_engine(
            *,
            config: object,
            repo_root: Path,
            prompt_text: str,
            raw_output_path: Path,
        ) -> str:
            del config, repo_root, prompt_text
            raw_output_path.write_text(json.dumps(review_payload), encoding="utf-8")
            return json.dumps(review_payload)

        def fake_run_gate(
            *,
            repo_root: Path,
            gate_script: Path,
            input_path: Path,
            output_path: Path,
            policy_path: Path | None = None,
        ) -> int:
            del repo_root, gate_script, input_path, policy_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("{}\n", encoding="utf-8")
            return 0

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            argv = [
                "run_review_engine.py",
                "--engine",
                "codex",
                "--scope-id",
                "issue-15",
                "--run-id",
                "run-test-layout",
                "--base-ref",
                "main",
                "--prompt-template",
                str(PROMPT_TEMPLATE),
                "--results-dir",
                ".scaffold/review_results",
            ]

            with (
                patch.object(self.runner, "_git_short_sha", side_effect=["abc1234", "def5678"]),
                patch.object(self.runner, "_git_has_worktree_changes", return_value=False),
                patch.object(self.runner, "_run_engine", side_effect=fake_run_engine),
                patch.object(self.runner, "_validate_schema", return_value=None),
                patch.object(self.runner, "_run_gate", side_effect=fake_run_gate),
                patch.object(sys, "argv", argv),
            ):
                old_cwd = Path.cwd()
                os.chdir(tmp_path)
                try:
                    exit_code = self.runner.main()
                finally:
                    os.chdir(old_cwd)

            self.assertEqual(exit_code, 0)

            run_root = tmp_path / ".scaffold/review_results/issue-15/run-test-layout/review-cycle"
            output_dir = run_root / "outputs"
            intermediate_dir = run_root / "intermediate"

            self.assertTrue((output_dir / "review.json").exists())
            self.assertTrue((output_dir / "review-cycle.result.json").exists())
            self.assertTrue((output_dir / "review-evidence.result.json").exists())
            self.assertTrue((output_dir / "index.json").exists())
            self.assertTrue((output_dir / "run-metadata.json").exists())

            self.assertTrue((intermediate_dir / "prompt.txt").exists())
            self.assertTrue((intermediate_dir / "raw-output.txt").exists())
            self.assertTrue((intermediate_dir / "review-cycle.input.json").exists())
            self.assertTrue((intermediate_dir / "review-evidence.input.json").exists())

            index_payload = json.loads((output_dir / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(
                index_payload["entrypoints"]["primary_review"],
                str(
                    Path(
                        ".scaffold/review_results/issue-15/run-test-layout/review-cycle/outputs/review.json"
                    )
                ),
            )

    def test_main_returns_nonzero_when_any_gate_fails(self) -> None:
        review_payload = {
            "status": "approved",
            "summary": "looks good",
            "findings": [],
        }

        def fake_run_engine(
            *,
            config: object,
            repo_root: Path,
            prompt_text: str,
            raw_output_path: Path,
        ) -> str:
            del config, repo_root, prompt_text
            raw_output_path.write_text(json.dumps(review_payload), encoding="utf-8")
            return json.dumps(review_payload)

        gate_exit_codes = [2, 0]

        def fake_run_gate(
            *,
            repo_root: Path,
            gate_script: Path,
            input_path: Path,
            output_path: Path,
            policy_path: Path | None = None,
        ) -> int:
            del repo_root, gate_script, input_path, policy_path
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("{}\n", encoding="utf-8")
            return gate_exit_codes.pop(0)

        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "run_review_engine.py",
                "--engine",
                "codex",
                "--scope-id",
                "issue-15",
                "--run-id",
                "run-test-fail",
                "--base-ref",
                "main",
                "--prompt-template",
                str(PROMPT_TEMPLATE),
            ]
            with (
                patch.object(self.runner, "_git_short_sha", side_effect=["abc1234", "def5678"]),
                patch.object(self.runner, "_git_has_worktree_changes", return_value=False),
                patch.object(self.runner, "_run_engine", side_effect=fake_run_engine),
                patch.object(self.runner, "_validate_schema", return_value=None),
                patch.object(self.runner, "_run_gate", side_effect=fake_run_gate),
                patch.object(sys, "argv", argv),
            ):
                old_cwd = Path.cwd()
                os.chdir(tmp)
                try:
                    exit_code = self.runner.main()
                finally:
                    os.chdir(old_cwd)

            self.assertEqual(exit_code, 2)

    def test_main_writes_failure_metadata_when_exception_occurs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            argv = [
                "run_review_engine.py",
                "--engine",
                "codex",
                "--scope-id",
                "issue-15",
                "--run-id",
                "run-test-exception",
                "--base-ref",
                "main",
                "--prompt-template",
                str(PROMPT_TEMPLATE),
                "--results-dir",
                ".scaffold/review_results",
            ]

            with (
                patch.object(self.runner, "_git_short_sha", side_effect=["abc1234", "def5678"]),
                patch.object(self.runner, "_git_has_worktree_changes", return_value=False),
                patch.object(self.runner, "_run_engine", side_effect=RuntimeError("engine boom")),
                patch.object(sys, "argv", argv),
            ):
                old_cwd = Path.cwd()
                os.chdir(tmp_path)
                try:
                    exit_code = self.runner.main()
                finally:
                    os.chdir(old_cwd)

            self.assertEqual(exit_code, 2)
            output_dir = (
                tmp_path
                / ".scaffold/review_results/issue-15/run-test-exception/review-cycle/outputs"
            )
            self.assertTrue((output_dir / "index.json").exists())
            self.assertTrue((output_dir / "run-metadata.json").exists())

            payload = json.loads((output_dir / "index.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "error")
            self.assertEqual(payload["review_cycle_exit_code"], 2)
            self.assertEqual(payload["review_evidence_exit_code"], 2)
            self.assertIn("engine boom", payload["error"])

    def test_main_fail_fast_when_head_or_base_sha_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "run_review_engine.py",
                "--engine",
                "codex",
                "--scope-id",
                "issue-15",
                "--run-id",
                "run-test-failfast",
                "--base-ref",
                "main",
                "--prompt-template",
                str(PROMPT_TEMPLATE),
            ]

            with (
                patch.object(self.runner, "_git_short_sha", side_effect=[None]),
                patch.object(sys, "argv", argv),
            ):
                old_cwd = Path.cwd()
                os.chdir(tmp)
                try:
                    head_fail_exit = self.runner.main()
                finally:
                    os.chdir(old_cwd)

            self.assertEqual(head_fail_exit, 2)

        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "run_review_engine.py",
                "--engine",
                "codex",
                "--scope-id",
                "issue-15",
                "--run-id",
                "run-test-failfast-base",
                "--base-ref",
                "main",
                "--prompt-template",
                str(PROMPT_TEMPLATE),
            ]

            with (
                patch.object(self.runner, "_git_short_sha", side_effect=["abc1234", None]),
                patch.object(sys, "argv", argv),
            ):
                old_cwd = Path.cwd()
                os.chdir(tmp)
                try:
                    base_fail_exit = self.runner.main()
                finally:
                    os.chdir(old_cwd)

            self.assertEqual(base_fail_exit, 2)

    def test_main_fail_fast_when_worktree_is_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "run_review_engine.py",
                "--engine",
                "codex",
                "--scope-id",
                "issue-15",
                "--run-id",
                "run-test-dirty-worktree",
                "--base-ref",
                "main",
                "--prompt-template",
                str(PROMPT_TEMPLATE),
            ]

            with (
                patch.object(self.runner, "_git_short_sha", side_effect=["abc1234", "def5678"]),
                patch.object(self.runner, "_git_has_worktree_changes", return_value=True),
                patch.object(sys, "argv", argv),
            ):
                old_cwd = Path.cwd()
                os.chdir(tmp)
                try:
                    exit_code = self.runner.main()
                finally:
                    os.chdir(old_cwd)

            self.assertEqual(exit_code, 2)


if __name__ == "__main__":
    unittest.main()
