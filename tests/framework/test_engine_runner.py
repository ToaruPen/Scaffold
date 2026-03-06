from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from framework.scripts.lib.engine_runner import _run_engine
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


if __name__ == "__main__":
    unittest.main()
