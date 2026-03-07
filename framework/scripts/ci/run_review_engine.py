#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from framework.scripts.lib.ci_helpers import (
    run_command as _ci_run_command,
)
from framework.scripts.lib.ci_helpers import (
    write_json as _write_json,
)
from framework.scripts.lib.engine_runner import (
    _extract_review_json,
    _normalize_review,
    _run_engine,
    _validate_schema,
)
from framework.scripts.lib.gates import _build_gate_input, _run_gate
from framework.scripts.lib.paths_metadata import (
    ReviewContext,
    RunnerConfig,
    RunPaths,
    RunResultState,
    _build_metadata,
    _build_run_paths,
    _relative_path,
)
from framework.scripts.lib.prompt import _load_prompt_template, _render_prompt


def _run_command(
    command: list[str],
    *,
    cwd: Path,
    timeout_sec: int,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return _ci_run_command(command, cwd=cwd, timeout_sec=timeout_sec, stdin_text=stdin_text)


def _git_short_sha(repo_root: Path, ref: str) -> str | None:
    result = _run_command(
        ["git", "rev-parse", "--short", ref],
        cwd=repo_root,
        timeout_sec=30,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def _git_has_worktree_changes(repo_root: Path) -> bool:
    result = _run_command(
        ["git", "status", "--short"],
        cwd=repo_root,
        timeout_sec=30,
    )
    if result.returncode != 0:
        raise ValueError("failed to inspect working tree status")
    return bool(result.stdout.strip())


def _resolve_review_range(repo_root: Path, base_ref: str) -> tuple[str, str]:
    head_sha = _git_short_sha(repo_root, "HEAD")
    if head_sha is None:
        raise ValueError(
            "failed to resolve HEAD sha; create an initial commit before running review"
        )

    base_sha = _git_short_sha(repo_root, base_ref)
    if base_sha is None:
        raise ValueError(f"failed to resolve base ref sha: {base_ref}")

    if _git_has_worktree_changes(repo_root):
        raise ValueError(
            "review-cycle requires a clean working tree; "
            "commit or stash changes before running review"
        )
    return head_sha, base_sha


def _parse_args() -> RunnerConfig:
    parser = argparse.ArgumentParser(description="Run codex/claude review and save JSON artifacts")
    parser.add_argument("--engine", choices=["codex", "claude"], required=True)
    parser.add_argument("--scope-id", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--base-ref", default="origin/main")
    parser.add_argument("--results-dir", default=".scaffold/review_results")
    parser.add_argument("--prompt-template", default="framework/config/review-engine-prompt.json")
    parser.add_argument(
        "--canonical-schema",
        default="framework/.agent/schemas/adapters/review-engine-result.schema.json",
    )
    parser.add_argument(
        "--codex-output-schema",
        default="framework/.agent/schemas/adapters/review-engine-result.codex-output.schema.json",
    )
    parser.add_argument("--policy", default="framework/config/review-evidence-policy.yaml")
    parser.add_argument("--timeout-sec", type=int, default=900)
    parser.add_argument(
        "--codex-model",
        default=os.getenv("SCAFFOLD_CODEX_MODEL"),
        help="Codex model override (or SCAFFOLD_CODEX_MODEL)",
    )
    parser.add_argument(
        "--claude-model",
        default=os.getenv("SCAFFOLD_CLAUDE_MODEL"),
        help="Claude model override (or SCAFFOLD_CLAUDE_MODEL)",
    )
    parser.add_argument(
        "--codex-reasoning-effort",
        default=os.getenv("SCAFFOLD_CODEX_REASONING_EFFORT"),
        help="Codex reasoning effort override via config (or SCAFFOLD_CODEX_REASONING_EFFORT)",
    )
    parser.add_argument(
        "--claude-effort",
        default=os.getenv("SCAFFOLD_CLAUDE_EFFORT"),
        help="Claude effort override (low|medium|high) or SCAFFOLD_CLAUDE_EFFORT",
    )
    parser.add_argument(
        "--declared-targets-file",
        default=os.getenv("SCAFFOLD_DECLARED_TARGETS_FILE"),
        help="Path to declared issue targets artifact for drift detection",
    )
    parser.add_argument(
        "--adr-index-file",
        default=os.getenv("SCAFFOLD_ADR_INDEX_FILE"),
        help="Path to ADR index artifact for adr-index-consistency gate",
    )
    args = parser.parse_args()

    run_id = args.run_id
    if not run_id:
        run_id = datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ")

    return RunnerConfig(
        engine=args.engine,
        scope_id=args.scope_id,
        run_id=run_id,
        base_ref=args.base_ref,
        results_dir=Path(args.results_dir),
        prompt_template=Path(args.prompt_template),
        canonical_schema=Path(args.canonical_schema),
        codex_schema=Path(args.codex_output_schema),
        policy_path=Path(args.policy),
        timeout_sec=args.timeout_sec,
        codex_model=args.codex_model,
        claude_model=args.claude_model,
        codex_reasoning_effort=args.codex_reasoning_effort,
        claude_effort=args.claude_effort,
        declared_targets_file=(
            Path(args.declared_targets_file) if args.declared_targets_file else None
        ),
        adr_index_file=(Path(args.adr_index_file) if args.adr_index_file else None),
    )


def main() -> int:
    config = _parse_args()
    repo_root = Path.cwd()
    try:
        head_sha, base_sha = _resolve_review_range(repo_root, config.base_ref)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    request_id = f"req-{config.engine}-{config.run_id}"
    paths = _build_run_paths(repo_root, config)
    artifact_path = _relative_path(repo_root, paths.review_json_path)
    context = ReviewContext(
        request_id=request_id,
        scope_id=config.scope_id,
        run_id=config.run_id,
        base_ref=config.base_ref,
        head_sha=head_sha,
        base_sha=base_sha,
        artifact_path=artifact_path,
        engine=config.engine,
    )

    try:
        normalized, cycle_exit, evidence_exit = _execute_review_pipeline(
            repo_root=repo_root,
            config=config,
            context=context,
            paths=paths,
        )

        metadata = _build_metadata(
            config=config,
            repo_root=repo_root,
            context=context,
            paths=paths,
            result_state=RunResultState(cycle_exit=cycle_exit, evidence_exit=evidence_exit),
        )
        _persist_metadata(paths=paths, metadata=metadata)

        print(json.dumps(metadata, ensure_ascii=True, indent=2, sort_keys=True))
        exit_code = 0 if cycle_exit == 0 and evidence_exit == 0 else 2
        return exit_code
    except Exception as exc:
        traceback.print_exc()
        failure_metadata = _build_metadata(
            config=config,
            repo_root=repo_root,
            context=context,
            paths=paths,
            result_state=RunResultState(
                cycle_exit=2,
                evidence_exit=2,
                status="error",
                error=str(exc),
                trace=traceback.format_exc(),
            ),
        )
        _persist_metadata(paths=paths, metadata=failure_metadata)
        print(json.dumps(failure_metadata, ensure_ascii=True, indent=2, sort_keys=True))
        return 2


def _execute_review_pipeline(
    *,
    repo_root: Path,
    config: RunnerConfig,
    context: ReviewContext,
    paths: RunPaths,
) -> tuple[dict[str, Any], int, int]:
    instructions, focus_paths = _load_prompt_template(repo_root / config.prompt_template)
    prompt_text = _render_prompt(
        instructions=instructions,
        focus_paths=focus_paths,
        context=context,
    )
    paths.prompt_path.write_text(prompt_text, encoding="utf-8")

    raw_text = _run_engine(
        config=config,
        repo_root=repo_root,
        prompt_text=prompt_text,
        raw_output_path=paths.raw_output_path,
    )

    extracted = _extract_review_json(raw_text)
    normalized = _normalize_review(payload=extracted, context=context)
    _write_json(paths.review_json_path, normalized)
    _validate_schema(repo_root, repo_root / config.canonical_schema, paths.review_json_path)

    _write_json(
        paths.review_cycle_input,
        _build_gate_input(
            artifact_path=context.artifact_path,
            review_payload=normalized,
            context=context,
        ),
    )
    cycle_exit = _run_gate(
        repo_root=repo_root,
        gate_script=repo_root / "framework/scripts/gates/validate_review_cycle.py",
        input_path=paths.review_cycle_input,
        output_path=paths.review_cycle_result,
    )

    review_evidence_artifact = _relative_path(repo_root, paths.review_evidence_result)
    _write_json(
        paths.review_evidence_input,
        _build_gate_input(
            artifact_path=review_evidence_artifact,
            review_payload=normalized,
            context=context,
        ),
    )
    evidence_exit = _run_gate(
        repo_root=repo_root,
        gate_script=repo_root / "framework/scripts/gates/validate_review_evidence.py",
        input_path=paths.review_evidence_input,
        output_path=paths.review_evidence_result,
        policy_path=repo_root / config.policy_path,
    )
    return normalized, cycle_exit, evidence_exit


def _persist_metadata(*, paths: RunPaths, metadata: dict[str, Any]) -> None:
    _write_json(paths.output_dir / "index.json", metadata)
    _write_json(paths.output_dir / "run-metadata.json", metadata)


if __name__ == "__main__":
    raise SystemExit(main())
