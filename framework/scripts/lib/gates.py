from __future__ import annotations

from pathlib import Path
from typing import Any

from framework.scripts.lib.ci_helpers import run_gate as _ci_run_gate
from framework.scripts.lib.paths_metadata import ReviewContext


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
