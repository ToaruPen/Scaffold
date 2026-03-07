from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Protocol, cast
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO_ROOT / "framework/scripts/ci/run_final_review.py"
PROMPT_TEMPLATE = REPO_ROOT / "framework/config/review-engine-prompt.json"


class _GateConfigLike(Protocol):
    intermediate_dir: Path
    output_dir: Path


def _extract_gate_config(kwargs: dict[str, object]) -> _GateConfigLike:
    config = kwargs.get("config")
    if config is None:
        raise AssertionError("missing config")
    if not hasattr(config, "intermediate_dir") or not hasattr(config, "output_dir"):
        raise AssertionError("invalid drift/adr gate config")
    return cast(_GateConfigLike, config)


def _load_runner_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_final_review_module", RUNNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_runner_main(
    *,
    runner: ModuleType,
    argv: list[str],
    cwd: Path,
    review_payload: Mapping[str, object],
    gate_exit_codes: list[int] | None = None,
) -> int:
    remaining_gate_exit_codes = list(gate_exit_codes or [])

    def fake_run_engine(
        *, config: object, repo_root: Path, prompt_text: str, raw_output_path: Path
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
        if remaining_gate_exit_codes:
            return remaining_gate_exit_codes.pop(0)
        return 0

    def fake_run_drift_and_adr_gates(**kwargs: object) -> tuple[int, int, Path, Path, Path, Path]:
        config = _extract_gate_config(kwargs)
        intermediate_dir = config.intermediate_dir
        output_dir = config.output_dir
        drift_input = intermediate_dir / "drift-detection.input.json"
        drift_result = output_dir / "drift-detection.result.json"
        adr_input = intermediate_dir / "adr-index.input.json"
        adr_result = output_dir / "adr-index.result.json"
        for path in (drift_input, drift_result, adr_input, adr_result):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
        return 0, 0, drift_input, drift_result, adr_input, adr_result

    with (
        patch.object(runner.shared, "_parse_args", side_effect=runner.shared._parse_args),
        patch.object(runner.shared, "_resolve_review_range", return_value=("abc1234", "def5678")),
        patch.object(runner, "_run_engine", side_effect=fake_run_engine),
        patch.object(runner, "_validate_schema", return_value=None),
        patch.object(runner, "_run_gate", side_effect=fake_run_gate),
        patch.object(runner, "run_drift_and_adr_gates", side_effect=fake_run_drift_and_adr_gates),
        patch.object(sys, "argv", argv),
    ):
        old_cwd = Path.cwd()
        os.chdir(cwd)
        try:
            return cast(int, runner.main())
        finally:
            os.chdir(old_cwd)


class RunFinalReviewTests(unittest.TestCase):
    runner: ModuleType

    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = _load_runner_module()

    def test_main_creates_stage_specific_layout(self) -> None:
        review_payload = {"status": "approved", "summary": "ok", "findings": []}

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            argv = [
                "run_final_review.py",
                "--engine",
                "codex",
                "--scope-id",
                "issue-12",
                "--run-id",
                "run-final-review",
                "--base-ref",
                "main",
                "--prompt-template",
                str(PROMPT_TEMPLATE),
                "--results-dir",
                ".scaffold/review_results",
            ]
            exit_code = _run_runner_main(
                runner=self.runner,
                argv=argv,
                cwd=tmp_path,
                review_payload=review_payload,
            )

            self.assertEqual(exit_code, 0)

            run_root = tmp_path / ".scaffold/review_results/issue-12/run-final-review/final-review"
            output_dir = run_root / "outputs"
            intermediate_dir = run_root / "intermediate"

            self.assertTrue((output_dir / "final-review.json").exists())
            self.assertTrue((output_dir / "final-review.result.json").exists())
            self.assertTrue((output_dir / "review-evidence.result.json").exists())
            self.assertTrue((output_dir / "drift-detection.result.json").exists())
            self.assertTrue((output_dir / "adr-index.result.json").exists())
            self.assertTrue((output_dir / "index.json").exists())
            self.assertTrue((output_dir / "run-metadata.json").exists())
            self.assertTrue((intermediate_dir / "prompt.txt").exists())
            self.assertTrue((intermediate_dir / "raw-output.txt").exists())
            self.assertTrue((intermediate_dir / "final-review.input.json").exists())
            self.assertTrue((intermediate_dir / "review-evidence.input.json").exists())
            self.assertTrue((intermediate_dir / "drift-detection.input.json").exists())
            self.assertTrue((intermediate_dir / "adr-index.input.json").exists())

            loaded_review = json.loads(
                (output_dir / "final-review.json").read_text(encoding="utf-8")
            )
            evidence_input = json.loads(
                (intermediate_dir / "review-evidence.input.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                evidence_input["artifact_path"], loaded_review["evidence"]["artifact_path"]
            )

    def test_main_returns_nonzero_when_gate_fails(self) -> None:
        review_payload = {"status": "approved", "summary": "ok", "findings": []}

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            argv = [
                "run_final_review.py",
                "--engine",
                "codex",
                "--scope-id",
                "issue-12",
                "--run-id",
                "run-final-review-fail",
                "--base-ref",
                "main",
                "--prompt-template",
                str(PROMPT_TEMPLATE),
            ]
            exit_code = _run_runner_main(
                runner=self.runner,
                argv=argv,
                cwd=tmp_path,
                review_payload=review_payload,
                gate_exit_codes=[2, 0, 0, 0],
            )

            self.assertEqual(exit_code, 2)

    def test_main_fail_fast_when_worktree_is_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            argv = [
                "run_final_review.py",
                "--engine",
                "codex",
                "--scope-id",
                "issue-12",
                "--run-id",
                "run-final-review-dirty",
                "--base-ref",
                "main",
                "--prompt-template",
                str(PROMPT_TEMPLATE),
            ]

            with (
                patch.object(
                    self.runner.shared, "_parse_args", side_effect=self.runner.shared._parse_args
                ),
                patch.object(
                    self.runner.shared,
                    "_resolve_review_range",
                    side_effect=ValueError(
                        "review-cycle requires a clean working tree; "
                        "commit or stash changes before running review"
                    ),
                ),
                patch.object(self.runner, "_run_engine") as run_engine_mock,
                patch.object(sys, "argv", argv),
            ):
                old_cwd = Path.cwd()
                os.chdir(tmp_path)
                try:
                    exit_code = self.runner.main()
                finally:
                    os.chdir(old_cwd)

            self.assertEqual(exit_code, 2)
            run_engine_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
