from __future__ import annotations

import json
from pathlib import Path

from framework.scripts.lib.paths_metadata import ReviewContext


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
