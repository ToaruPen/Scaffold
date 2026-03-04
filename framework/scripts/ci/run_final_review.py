#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from framework.scripts.ci import run_review_engine as shared
from framework.scripts.lib.final_review_helpers import DriftAdrGateConfig, run_drift_and_adr_gates

_STAGE = "final-review"


def main() -> int:
    config = shared._parse_args()
    repo_root = Path.cwd()

    head_sha = shared._git_short_sha(repo_root, "HEAD")
    if head_sha is None:
        print(
            "failed to resolve HEAD sha; create an initial commit before running review",
            file=sys.stderr,
        )
        return 2
    base_sha = shared._git_short_sha(repo_root, config.base_ref)
    if base_sha is None:
        print(f"failed to resolve base ref sha: {config.base_ref}", file=sys.stderr)
        return 2

    request_id = f"req-{config.engine}-{_STAGE}-{config.run_id}"
    run_dir = repo_root / config.results_dir / config.scope_id / config.run_id / _STAGE
    output_dir = run_dir / "outputs"
    intermediate_dir = run_dir / "intermediate"
    output_dir.mkdir(parents=True, exist_ok=True)
    intermediate_dir.mkdir(parents=True, exist_ok=True)

    review_json_path = output_dir / f"{_STAGE}.json"
    artifact_path = shared._relative_path(repo_root, review_json_path)
    context = shared.ReviewContext(
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
        instructions, focus_paths = shared._load_prompt_template(repo_root / config.prompt_template)
        prompt_text = shared._render_prompt(
            instructions=instructions,
            focus_paths=focus_paths,
            context=context,
        )
        (intermediate_dir / "prompt.txt").write_text(prompt_text, encoding="utf-8")

        raw_output_path = intermediate_dir / "raw-output.txt"
        raw_text = shared._run_engine(
            config=config,
            repo_root=repo_root,
            prompt_text=prompt_text,
            raw_output_path=raw_output_path,
        )

        extracted = shared._extract_review_json(raw_text)
        normalized = shared._normalize_review(
            payload=extracted,
            context=context,
        )
        shared._write_json(review_json_path, normalized)
        shared._validate_schema(repo_root, repo_root / config.canonical_schema, review_json_path)

        stage_input = intermediate_dir / f"{_STAGE}.input.json"
        stage_result = output_dir / f"{_STAGE}.result.json"
        shared._write_json(
            stage_input,
            shared._build_gate_input(
                artifact_path=artifact_path,
                review_payload=normalized,
                context=context,
            ),
        )
        stage_exit = shared._run_gate(
            repo_root=repo_root,
            gate_script=repo_root / "framework/scripts/gates/validate_final_review.py",
            input_path=stage_input,
            output_path=stage_result,
        )

        evidence_input = intermediate_dir / "review-evidence.input.json"
        evidence_result = output_dir / "review-evidence.result.json"
        evidence_artifact = shared._relative_path(repo_root, evidence_result)
        shared._write_json(
            evidence_input,
            shared._build_gate_input(
                artifact_path=evidence_artifact,
                review_payload=normalized,
                context=context,
            ),
        )
        evidence_exit = shared._run_gate(
            repo_root=repo_root,
            gate_script=repo_root / "framework/scripts/gates/validate_review_evidence.py",
            input_path=evidence_input,
            output_path=evidence_result,
            policy_path=repo_root / config.policy_path,
        )

        drift_exit, adr_exit, drift_input, drift_result, adr_input, adr_result = (
            run_drift_and_adr_gates(
                repo_root=repo_root,
                base_ref=config.base_ref,
                context=context,
                config=DriftAdrGateConfig(
                    results_dir=config.results_dir,
                    intermediate_dir=intermediate_dir,
                    output_dir=output_dir,
                    declared_targets_file=config.declared_targets_file,
                    adr_index_file=config.adr_index_file,
                ),
            )
        )

        metadata = {
            "stage": _STAGE,
            "engine": config.engine,
            "scope_id": config.scope_id,
            "run_id": config.run_id,
            "request_id": request_id,
            "head_sha": head_sha,
            "base_ref": config.base_ref,
            "base_sha": base_sha,
            "run_dir": shared._relative_path(repo_root, run_dir),
            "output_dir": shared._relative_path(repo_root, output_dir),
            "intermediate_dir": shared._relative_path(repo_root, intermediate_dir),
            "review_json": artifact_path,
            "stage_result": shared._relative_path(repo_root, stage_result),
            "review_evidence_result": shared._relative_path(repo_root, evidence_result),
            "drift_detection_result": shared._relative_path(repo_root, drift_result),
            "adr_index_result": shared._relative_path(repo_root, adr_result),
            "stage_input": shared._relative_path(repo_root, stage_input),
            "review_evidence_input": shared._relative_path(repo_root, evidence_input),
            "drift_detection_input": shared._relative_path(repo_root, drift_input),
            "adr_index_input": shared._relative_path(repo_root, adr_input),
            "raw_output": shared._relative_path(repo_root, raw_output_path),
            "prompt": shared._relative_path(repo_root, intermediate_dir / "prompt.txt"),
            "stage_exit_code": stage_exit,
            "review_evidence_exit_code": evidence_exit,
            "drift_detection_exit_code": drift_exit,
            "adr_index_exit_code": adr_exit,
            "configured_model": config.codex_model
            if config.engine == "codex"
            else config.claude_model,
            "configured_effort": (
                config.codex_reasoning_effort if config.engine == "codex" else config.claude_effort
            ),
            "entrypoints": {
                "primary_review": shared._relative_path(repo_root, review_json_path),
                "final_review_gate_result": shared._relative_path(repo_root, stage_result),
                "review_evidence_gate_result": shared._relative_path(repo_root, evidence_result),
                "drift_detection_gate_result": shared._relative_path(repo_root, drift_result),
                "adr_index_gate_result": shared._relative_path(repo_root, adr_result),
            },
        }
        shared._write_json(output_dir / "index.json", metadata)
        shared._write_json(output_dir / "run-metadata.json", metadata)

        print(json.dumps(metadata, ensure_ascii=True, indent=2, sort_keys=True))
        return (
            0 if stage_exit == 0 and evidence_exit == 0 and drift_exit == 0 and adr_exit == 0 else 2
        )
    except Exception as exc:
        traceback.print_exc()
        error_metadata = {
            "stage": _STAGE,
            "engine": config.engine,
            "scope_id": config.scope_id,
            "run_id": config.run_id,
            "request_id": request_id,
            "head_sha": head_sha,
            "base_ref": config.base_ref,
            "base_sha": base_sha,
            "run_dir": shared._relative_path(repo_root, run_dir),
            "output_dir": shared._relative_path(repo_root, output_dir),
            "intermediate_dir": shared._relative_path(repo_root, intermediate_dir),
            "review_json": artifact_path,
            "status": "error",
            "error": str(exc),
            "stage_exit_code": 2,
            "review_evidence_exit_code": 2,
            "drift_detection_exit_code": 2,
            "adr_index_exit_code": 2,
        }
        shared._write_json(output_dir / "index.json", error_metadata)
        shared._write_json(output_dir / "run-metadata.json", error_metadata)
        print(json.dumps(error_metadata, ensure_ascii=True, indent=2, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
