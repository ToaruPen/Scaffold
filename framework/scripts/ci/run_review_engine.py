#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from framework.scripts.lib.ci_helpers import (
        relative_path as _ci_relative_path,
    )
    from framework.scripts.lib.ci_helpers import (
        run_command as _ci_run_command,
    )
    from framework.scripts.lib.ci_helpers import (
        run_gate as _ci_run_gate,
    )
    from framework.scripts.lib.ci_helpers import (
        write_json as _ci_write_json,
    )
    from framework.scripts.lib.schema_validator import (
        validate_schema_file as _validate_schema_file,
    )
except ModuleNotFoundError:
    repo_root = Path(__file__).resolve().parents[3]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from framework.scripts.lib.ci_helpers import (
        relative_path as _ci_relative_path,
    )
    from framework.scripts.lib.ci_helpers import (
        run_command as _ci_run_command,
    )
    from framework.scripts.lib.ci_helpers import (
        run_gate as _ci_run_gate,
    )
    from framework.scripts.lib.ci_helpers import (
        write_json as _ci_write_json,
    )
    from framework.scripts.lib.schema_validator import (
        validate_schema_file as _validate_schema_file,
    )


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


def _stream_to_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return ""


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


def _load_prompt_template(path: Path) -> tuple[list[str], list[str]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"failed to load prompt template: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("prompt template must be a JSON object")

    version = payload.get("template_version")
    if version != 1:
        raise ValueError("prompt template version must be 1")

    instructions_raw = payload.get("instructions")
    if not isinstance(instructions_raw, list) or not instructions_raw:
        raise ValueError("prompt template instructions must be a non-empty array")
    instructions: list[str] = []
    for item in instructions_raw:
        if not isinstance(item, str):
            raise ValueError("prompt template instructions must contain strings")
        instructions.append(item)

    focus_raw = payload.get("focus_paths", [])
    if not isinstance(focus_raw, list):
        raise ValueError("prompt template focus_paths must be an array")
    focus_paths: list[str] = []
    for item in focus_raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("prompt template focus_paths must contain non-empty strings")
        focus_paths.append(item)
    return instructions, focus_paths


def _render_prompt(
    *,
    instructions: list[str],
    focus_paths: list[str],
    context: ReviewContext,
) -> str:
    lines = list(instructions)
    lines.extend(
        [
            "",
            "Execution context:",
            f"- scope_id: {context.scope_id}",
            f"- run_id: {context.run_id}",
            f"- base_ref: {context.base_ref}",
            "- compare target: current committed branch changes against base_ref",
            "",
            "Required fixed output values:",
            f"- request_id: {context.request_id}",
            f"- scope_id: {context.scope_id}",
            f"- run_id: {context.run_id}",
            f"- evidence.head_sha: {context.head_sha}",
            f"- evidence.base_sha: {context.base_sha if context.base_sha else 'null'}",
            f"- evidence.artifact_path: {context.artifact_path}",
            f"- provider_metadata.provider: {context.engine}",
            "- provider_metadata.model: null",
            "- provider_metadata.duration_ms: null",
        ]
    )
    if focus_paths:
        lines.append("")
        lines.append("Focus paths:")
        lines.extend(f"- {item}" for item in focus_paths)
    return "\n".join(lines) + "\n"


def _decode_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def _decode_first_json_object(text: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    return None


def _extract_review_json(raw_text: str) -> dict[str, Any]:
    direct = _decode_json_object(raw_text)
    if direct is not None:
        nested = direct.get("result")
        if isinstance(nested, str):
            candidate = _decode_json_object(nested)
            if candidate is not None:
                return candidate
            found = _decode_first_json_object(nested)
            if found is not None:
                return found
        return direct

    found = _decode_first_json_object(raw_text)
    if found is not None:
        nested = found.get("result")
        if isinstance(nested, str):
            candidate = _decode_json_object(nested)
            if candidate is not None:
                return candidate
            nested_found = _decode_first_json_object(nested)
            if nested_found is not None:
                return nested_found
        return found

    raise ValueError("could not extract JSON object from review output")


def _normalize_review(
    *,
    payload: dict[str, Any],
    context: ReviewContext,
) -> dict[str, Any]:
    status = payload.get("status")
    summary = payload.get("summary")
    findings = payload.get("findings")
    if not isinstance(status, str):
        raise ValueError("review output missing status")
    if not isinstance(summary, str):
        raise ValueError("review output missing summary")
    if not isinstance(findings, list):
        raise ValueError("review output missing findings array")

    provider_metadata = payload.get("provider_metadata")
    if not isinstance(provider_metadata, dict):
        provider_metadata = {}

    normalized_provider_metadata: dict[str, Any] = {"provider": context.engine}
    model = provider_metadata.get("model")
    if isinstance(model, str) and model:
        normalized_provider_metadata["model"] = model
    duration_ms = provider_metadata.get("duration_ms")
    if isinstance(duration_ms, int) and duration_ms >= 0:
        normalized_provider_metadata["duration_ms"] = duration_ms

    normalized: dict[str, Any] = {
        "request_id": context.request_id,
        "scope_id": context.scope_id,
        "run_id": context.run_id,
        "status": status,
        "summary": summary,
        "findings": findings,
        "evidence": {
            "head_sha": context.head_sha,
            "artifact_path": context.artifact_path,
            "created_at": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        },
        "provider_metadata": normalized_provider_metadata,
    }
    if context.base_sha is not None:
        normalized["evidence"]["base_sha"] = context.base_sha
    return normalized


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _ci_write_json(path, payload)


def _validate_schema(repo_root: Path, schema_path: Path, target_path: Path) -> None:
    _validate_schema_file(
        repo_root=repo_root,
        schema_path=schema_path,
        target_path=target_path,
        timeout_sec=60,
        command_runner=_run_command,
    )


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


def _run_gate(
    *,
    repo_root: Path,
    gate_script: Path,
    input_path: Path,
    output_path: Path,
    policy_path: Path | None = None,
) -> int:
    return _ci_run_gate(
        repo_root=repo_root,
        gate_script=gate_script,
        input_path=input_path,
        output_path=output_path,
        policy_path=policy_path,
    )


def _build_gate_input(
    *,
    artifact_path: str,
    review_payload: dict[str, Any],
    context: ReviewContext,
) -> dict[str, Any]:
    expected: dict[str, Any] = {"head_sha": context.head_sha}
    if context.base_sha is not None:
        expected["base_sha"] = context.base_sha
    return {
        "request_id": context.request_id,
        "scope_id": context.scope_id,
        "run_id": context.run_id,
        "artifact_path": artifact_path,
        "expected": expected,
        "review": review_payload,
    }


def _run_engine(
    *,
    config: RunnerConfig,
    repo_root: Path,
    prompt_text: str,
    raw_output_path: Path,
) -> str:
    if config.engine == "codex":
        command = ["codex", "exec"]
        if config.codex_model:
            command.extend(["--model", config.codex_model])
        if config.codex_reasoning_effort:
            command.extend(["-c", f"model_reasoning_effort={config.codex_reasoning_effort}"])
        command.extend(
            [
                "--full-auto",
                "--sandbox",
                "read-only",
                "--output-schema",
                str(config.codex_schema),
                "--output-last-message",
                str(raw_output_path),
                "-",
            ]
        )
        result = _run_command(
            command,
            cwd=repo_root,
            timeout_sec=config.timeout_sec,
            stdin_text=prompt_text,
        )
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise ValueError(f"codex execution failed: {message}")
        if raw_output_path.exists():
            return raw_output_path.read_text(encoding="utf-8")
        return result.stdout

    schema_text = json.dumps(
        json.loads(config.canonical_schema.read_text(encoding="utf-8")), separators=(",", ":")
    )
    command = [
        "claude",
        "-p",
        "--permission-mode",
        "bypassPermissions",
        "--output-format",
        "json",
        "--json-schema",
        schema_text,
        prompt_text,
    ]
    if config.claude_model:
        command[1:1] = ["--model", config.claude_model]
    if config.claude_effort:
        command[1:1] = ["--effort", config.claude_effort]
    result = _run_command(command, cwd=repo_root, timeout_sec=config.timeout_sec)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise ValueError(f"claude execution failed: {message}")
    raw_output_path.write_text(result.stdout, encoding="utf-8")
    return result.stdout


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
        normalized = _normalize_review(
            payload=extracted,
            context=context,
        )
        _write_json(paths.review_json_path, normalized)

        _validate_schema(repo_root, repo_root / config.canonical_schema, paths.review_json_path)

        review_cycle_artifact = context.artifact_path
        _write_json(
            paths.review_cycle_input,
            _build_gate_input(
                artifact_path=review_cycle_artifact,
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

        metadata = _build_metadata(
            config=config,
            repo_root=repo_root,
            context=context,
            paths=paths,
            result_state=RunResultState(cycle_exit=cycle_exit, evidence_exit=evidence_exit),
        )
        _write_json(paths.output_dir / "index.json", metadata)
        _write_json(paths.output_dir / "run-metadata.json", metadata)

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
        _write_json(paths.output_dir / "index.json", failure_metadata)
        _write_json(paths.output_dir / "run-metadata.json", failure_metadata)
        print(json.dumps(failure_metadata, ensure_ascii=True, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
