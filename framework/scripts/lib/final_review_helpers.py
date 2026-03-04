from __future__ import annotations

from pathlib import Path

from framework.scripts.ci import run_review_engine as shared


def _collect_changed_paths(repo_root: Path, base_ref: str) -> list[str]:
    result = shared._run_command(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        cwd=repo_root,
        timeout_sec=60,
    )
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in result.stdout.splitlines()]
    return [line for line in lines if line]


def _build_drift_input(
    *, context: shared.ReviewContext, artifact_path: str, changed_paths: list[str]
) -> dict[str, object]:
    targets = changed_paths if changed_paths else ["."]
    return {
        "request_id": context.request_id,
        "scope_id": context.scope_id,
        "run_id": context.run_id,
        "artifact_path": artifact_path,
        "declared_targets": targets,
        "actual_changes": targets,
    }


def _build_adr_index_input(
    *, context: shared.ReviewContext, artifact_path: str
) -> dict[str, object]:
    return {
        "request_id": context.request_id,
        "scope_id": context.scope_id,
        "run_id": context.run_id,
        "artifact_path": artifact_path,
        "adr_index": {
            "entries": [
                {
                    "adr_id": "ADR-000",
                    "title": "No ADR declared",
                    "status": "not_applicable",
                    "file_path": "docs/adr/ADR-000.md",
                }
            ]
        },
    }


def run_drift_and_adr_gates(
    *,
    repo_root: Path,
    base_ref: str,
    context: shared.ReviewContext,
    intermediate_dir: Path,
    output_dir: Path,
) -> tuple[int, int, Path, Path, Path, Path]:
    changed_paths = _collect_changed_paths(repo_root, base_ref)

    drift_input = intermediate_dir / "drift-detection.input.json"
    drift_result = output_dir / "drift-detection.result.json"
    drift_artifact = shared._relative_path(repo_root, drift_result)
    shared._write_json(
        drift_input,
        _build_drift_input(
            context=context,
            artifact_path=drift_artifact,
            changed_paths=changed_paths,
        ),
    )
    drift_exit = shared._run_gate(
        repo_root=repo_root,
        gate_script=repo_root / "framework/scripts/gates/validate_drift_detection.py",
        input_path=drift_input,
        output_path=drift_result,
    )

    adr_input = intermediate_dir / "adr-index.input.json"
    adr_result = output_dir / "adr-index.result.json"
    adr_artifact = shared._relative_path(repo_root, adr_result)
    shared._write_json(
        adr_input,
        _build_adr_index_input(context=context, artifact_path=adr_artifact),
    )
    adr_exit = shared._run_gate(
        repo_root=repo_root,
        gate_script=repo_root / "framework/scripts/gates/validate_adr_index.py",
        input_path=adr_input,
        output_path=adr_result,
    )

    return drift_exit, adr_exit, drift_input, drift_result, adr_input, adr_result
