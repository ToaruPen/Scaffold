from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from framework.scripts.lib.ci_helpers import run_command as _ci_run_command
from framework.scripts.lib.ci_helpers import write_json as _ci_write_json
from framework.scripts.lib.paths_metadata import ReviewContext, RunnerConfig
from framework.scripts.lib.schema_validator import validate_schema_file as _validate_schema_file


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
        command_runner=_ci_run_command,
    )


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
        result = _ci_run_command(
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

    if config.engine == "claude":
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
        result = _ci_run_command(command, cwd=repo_root, timeout_sec=config.timeout_sec)
        if result.returncode != 0:
            message = result.stderr.strip() or result.stdout.strip()
            raise ValueError(f"claude execution failed: {message}")
        raw_output_path.write_text(result.stdout, encoding="utf-8")
        return result.stdout

    raise ValueError(f"unsupported engine: {config.engine}")
