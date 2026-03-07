from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from framework.scripts.lib.ci_helpers import relative_path as _ci_relative_path


@dataclass(frozen=True)
class RunnerConfig:
    engine: str
    scope_id: str
    run_id: str
    base_ref: str
    results_dir: Path
    prompt_template: Path
    canonical_schema: Path
    codex_schema: Path
    policy_path: Path
    timeout_sec: int
    codex_model: str | None
    claude_model: str | None
    codex_reasoning_effort: str | None
    claude_effort: str | None
    declared_targets_file: Path | None
    adr_index_file: Path | None


@dataclass(frozen=True)
class ReviewContext:
    request_id: str
    scope_id: str
    run_id: str
    base_ref: str
    head_sha: str
    base_sha: str | None
    artifact_path: str
    engine: str


@dataclass(frozen=True)
class RunPaths:
    run_dir: Path
    output_dir: Path
    intermediate_dir: Path
    review_json_path: Path
    prompt_path: Path
    raw_output_path: Path
    review_cycle_input: Path
    review_cycle_result: Path
    review_evidence_input: Path
    review_evidence_result: Path


@dataclass(frozen=True)
class RunResultState:
    cycle_exit: int
    evidence_exit: int
    status: str | None = None
    error: str | None = None
    trace: str | None = None


def _relative_path(repo_root: Path, path: Path) -> str:
    return _ci_relative_path(repo_root, path)


def _optional_relative_path(repo_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    candidate = path if path.is_absolute() else repo_root / path
    return _relative_path(repo_root, candidate)


def _build_optional_metadata(config: RunnerConfig, repo_root: Path) -> dict[str, str | None]:
    return {
        "declared_targets_file": _optional_relative_path(repo_root, config.declared_targets_file),
        "adr_index_file": _optional_relative_path(repo_root, config.adr_index_file),
    }


def _build_run_paths(repo_root: Path, config: RunnerConfig) -> RunPaths:
    run_dir = repo_root / config.results_dir / config.scope_id / config.run_id / "review-cycle"
    output_dir = run_dir / "outputs"
    intermediate_dir = run_dir / "intermediate"
    output_dir.mkdir(parents=True, exist_ok=True)
    intermediate_dir.mkdir(parents=True, exist_ok=True)
    return RunPaths(
        run_dir=run_dir,
        output_dir=output_dir,
        intermediate_dir=intermediate_dir,
        review_json_path=output_dir / "review.json",
        prompt_path=intermediate_dir / "prompt.txt",
        raw_output_path=intermediate_dir / "raw-output.txt",
        review_cycle_input=intermediate_dir / "review-cycle.input.json",
        review_cycle_result=output_dir / "review-cycle.result.json",
        review_evidence_input=intermediate_dir / "review-evidence.input.json",
        review_evidence_result=output_dir / "review-evidence.result.json",
    )


def _build_metadata(
    *,
    config: RunnerConfig,
    repo_root: Path,
    context: ReviewContext,
    paths: RunPaths,
    result_state: RunResultState,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "engine": config.engine,
        "scope_id": config.scope_id,
        "run_id": config.run_id,
        "request_id": context.request_id,
        "head_sha": context.head_sha,
        "base_ref": config.base_ref,
        "base_sha": context.base_sha,
        "run_dir": _relative_path(repo_root, paths.run_dir),
        "output_dir": _relative_path(repo_root, paths.output_dir),
        "intermediate_dir": _relative_path(repo_root, paths.intermediate_dir),
        "review_json": context.artifact_path,
        "review_cycle_result": _relative_path(repo_root, paths.review_cycle_result),
        "review_evidence_result": _relative_path(repo_root, paths.review_evidence_result),
        "review_cycle_input": _relative_path(repo_root, paths.review_cycle_input),
        "review_evidence_input": _relative_path(repo_root, paths.review_evidence_input),
        "raw_output": _relative_path(repo_root, paths.raw_output_path),
        "prompt": _relative_path(repo_root, paths.prompt_path),
        "review_cycle_exit_code": result_state.cycle_exit,
        "review_evidence_exit_code": result_state.evidence_exit,
        "configured_model": (
            config.codex_model if config.engine == "codex" else config.claude_model
        ),
        "configured_effort": (
            config.codex_reasoning_effort if config.engine == "codex" else config.claude_effort
        ),
        **_build_optional_metadata(config, repo_root),
        "entrypoints": {
            "primary_review": context.artifact_path,
            "review_cycle_gate_result": _relative_path(repo_root, paths.review_cycle_result),
            "review_evidence_gate_result": _relative_path(repo_root, paths.review_evidence_result),
        },
    }
    if result_state.status is not None:
        metadata["status"] = result_state.status
    if result_state.error is not None:
        metadata["error"] = result_state.error
    if result_state.trace is not None:
        metadata["traceback"] = result_state.trace
    return metadata
