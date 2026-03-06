from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from framework.scripts.lib.ci_helpers import relative_path, run_command, run_gate, write_json
from framework.scripts.lib.paths_metadata import ReviewContext


@dataclass(frozen=True)
class DriftAdrGateConfig:
    results_dir: Path
    intermediate_dir: Path
    output_dir: Path
    declared_targets_file: Path | None
    adr_index_file: Path | None


def _collect_changed_paths(repo_root: Path, base_ref: str) -> list[str]:
    command = ["git", "diff", "--name-only", f"{base_ref}...HEAD"]
    result = run_command(
        command,
        cwd=repo_root,
        timeout_sec=60,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            command,
            output=result.stdout,
            stderr=result.stderr,
        )
    lines = [line.strip() for line in result.stdout.splitlines()]
    return [line for line in lines if line]


def _build_drift_input(
    *,
    context: ReviewContext,
    artifact_path: str,
    declared_targets: list[str],
    changed_paths: list[str],
) -> dict[str, object]:
    actual_changes = changed_paths if changed_paths else []
    declared = declared_targets if declared_targets else ["__missing_declared_targets__"]
    return {
        "request_id": context.request_id,
        "scope_id": context.scope_id,
        "run_id": context.run_id,
        "artifact_path": artifact_path,
        "declared_targets": declared,
        "actual_changes": actual_changes,
    }


def _build_adr_index_input(
    *,
    context: ReviewContext,
    artifact_path: str,
    entries: list[dict[str, Any]],
) -> dict[str, object]:
    return {
        "request_id": context.request_id,
        "scope_id": context.scope_id,
        "run_id": context.run_id,
        "artifact_path": artifact_path,
        "adr_index": {"entries": entries},
    }


def _resolve_existing_path(
    repo_root: Path,
    configured: Path | None,
    candidates: list[Path],
) -> Path | None:
    paths: list[Path] = []
    if configured is not None:
        paths.append(configured if configured.is_absolute() else repo_root / configured)
    paths.extend(candidates)
    for path in paths:
        if path.exists():
            return path
    return None


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _extract_targets(payload: dict[str, Any]) -> list[str]:
    direct = payload.get("declared_targets")
    if isinstance(direct, list):
        normalized = [item.strip() for item in direct if isinstance(item, str) and item.strip()]
        if normalized:
            return normalized

    change_targets = payload.get("change_targets")
    if isinstance(change_targets, list):
        normalized = [
            item.strip() for item in change_targets if isinstance(item, str) and item.strip()
        ]
        if normalized:
            return normalized

    issue = payload.get("issue")
    if isinstance(issue, dict):
        issue_targets = issue.get("change_targets")
        if isinstance(issue_targets, list):
            normalized = [
                item.strip() for item in issue_targets if isinstance(item, str) and item.strip()
            ]
            if normalized:
                return normalized
    return []


def _load_declared_targets(
    *,
    repo_root: Path,
    results_dir: Path,
    context: ReviewContext,
    declared_targets_file: Path | None,
) -> list[str]:
    results_root = results_dir if results_dir.is_absolute() else repo_root / results_dir
    candidates = [
        results_root / context.scope_id / context.run_id / "issue-targets.result.json",
        results_root / context.scope_id / "issue-targets.result.json",
        repo_root / ".scaffold" / "issue-targets" / f"{context.scope_id}.json",
        repo_root / ".scaffold" / "issue-targets" / f"{context.scope_id}.result.json",
    ]
    path = _resolve_existing_path(repo_root, declared_targets_file, candidates)
    if path is None:
        return []
    payload = _read_json_object(path)
    if payload is None:
        return []
    return _extract_targets(payload)


def _load_adr_entries(
    *,
    repo_root: Path,
    adr_index_file: Path | None,
) -> list[dict[str, Any]]:
    candidates = [
        repo_root / "docs" / "adr" / "index.json",
        repo_root / "docs" / "adr" / "adr-index.json",
        repo_root / ".scaffold" / "adr-index.json",
    ]
    path = _resolve_existing_path(repo_root, adr_index_file, candidates)
    if path is None:
        return []
    payload = _read_json_object(path)
    if payload is None:
        return []

    entries = payload.get("entries")
    if isinstance(entries, list):
        return [entry for entry in entries if isinstance(entry, dict)]
    adr_index = payload.get("adr_index")
    if isinstance(adr_index, dict):
        nested_entries = adr_index.get("entries")
        if isinstance(nested_entries, list):
            return [entry for entry in nested_entries if isinstance(entry, dict)]
    return []


def run_drift_and_adr_gates(
    *,
    repo_root: Path,
    base_ref: str,
    context: ReviewContext,
    config: DriftAdrGateConfig,
) -> tuple[int, int, Path, Path, Path, Path]:
    changed_paths = _collect_changed_paths(repo_root, base_ref)
    declared_targets = _load_declared_targets(
        repo_root=repo_root,
        results_dir=config.results_dir,
        context=context,
        declared_targets_file=config.declared_targets_file,
    )
    adr_entries = _load_adr_entries(repo_root=repo_root, adr_index_file=config.adr_index_file)

    drift_input = config.intermediate_dir / "drift-detection.input.json"
    drift_result = config.output_dir / "drift-detection.result.json"
    drift_artifact = relative_path(repo_root, drift_result)
    write_json(
        drift_input,
        _build_drift_input(
            context=context,
            artifact_path=drift_artifact,
            declared_targets=declared_targets,
            changed_paths=changed_paths,
        ),
    )
    drift_exit = run_gate(
        repo_root=repo_root,
        gate_script=repo_root / "framework/scripts/gates/validate_drift_detection.py",
        input_path=drift_input,
        output_path=drift_result,
    )

    adr_input = config.intermediate_dir / "adr-index.input.json"
    adr_result = config.output_dir / "adr-index.result.json"
    adr_artifact = relative_path(repo_root, adr_result)
    write_json(
        adr_input,
        _build_adr_index_input(
            context=context,
            artifact_path=adr_artifact,
            entries=adr_entries,
        ),
    )
    adr_exit = run_gate(
        repo_root=repo_root,
        gate_script=repo_root / "framework/scripts/gates/validate_adr_index.py",
        input_path=adr_input,
        output_path=adr_result,
    )

    return drift_exit, adr_exit, drift_input, drift_result, adr_input, adr_result
