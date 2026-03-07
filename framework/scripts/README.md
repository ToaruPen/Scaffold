# framework/scripts/

Distributable script layer for consumer repositories.

## Subdirectories

- `framework/scripts/gates/`: deterministic pass/fail validators
- `framework/scripts/lint/`: schema/template/static checks
- `framework/scripts/ci/`: CI entrypoint orchestration
- `framework/scripts/hooks/`: local git hook wrappers
- `framework/scripts/lib/`: shared helper code

## Rules

- Keep validators deterministic and side-effect-free.
- One validator per artifact contract.
- Do not put policy prose in validator scripts.
- Add matching tests under `tests/framework/` for every behavior change.

## Contract Inventory

`framework/scripts/manifest.yaml` is the executable source of truth for:

- `contracts`: gate definitions and validator bindings
- `must_command_contracts`: command-to-contract requirements
- `command_tiers`: command execution surface classification (`core` / `conditional`)

## Adapter Stubs

- `framework/scripts/lib/review_engine_stub.py`
- `framework/scripts/lib/vcs_stub.py`
- `framework/scripts/lib/bot_stub.py`

## Shared utility modules

- `framework/scripts/lib/contract_loader.py`
  - Loads `framework/scripts/manifest.yaml` safely and provides contract lookup helpers.
- `framework/scripts/lib/schema_validator.py`
  - Shared JSON/YAML schema validation wrapper over `check-jsonschema`.
- `framework/scripts/lib/exit_codes.py`
  - Centralized exit code constants shared by CI/gate scripts.

## Review runner

- `framework/scripts/ci/run_review_engine.py`
  - Runs `codex` or `claude` in read-only review mode.
  - Requires a clean working tree so review evidence stays linked to commit/range.
  - Creates artifacts under `.scaffold/review_results/<scope_id>/<run_id>/review-cycle/`.
  - Separates final outputs from intermediate files:
    - `outputs/review.json`
    - `outputs/review-cycle.result.json`
    - `outputs/review-evidence.result.json`
    - `outputs/index.json` (entrypoint map; check this first)
    - `outputs/run-metadata.json`
    - `intermediate/prompt.txt`
    - `intermediate/raw-output.txt`
    - `intermediate/review-cycle.input.json`
    - `intermediate/review-evidence.input.json`
  - Uses stable fixed filenames in each directory (no per-file engine prefixes).
  - Primary artifact is always `outputs/review.json`.
  - Uses prompt template: `framework/config/review-engine-prompt.json`.
  - Model can be controlled externally:
    - CLI: `--codex-model`, `--claude-model`
    - Env: `SCAFFOLD_CODEX_MODEL`, `SCAFFOLD_CLAUDE_MODEL`
  - Reasoning/effort can be controlled externally:
    - CLI: `--codex-reasoning-effort`, `--claude-effort`
    - Env: `SCAFFOLD_CODEX_REASONING_EFFORT`, `SCAFFOLD_CLAUDE_EFFORT`
  - Claude review-cycle uses a read-only tool profile instead of permission bypass:
    - Permission mode: `dontAsk`
    - Built-in tools: `Read`, `Glob`, `Grep`, `LS`, `Bash`
    - Allowed Bash patterns are limited to repository inspection commands such as `git status/log/diff/show/rev-parse/merge-base/branch/remote`, `rg`, `sg`, `ls`, and `pwd`
    - Example high-depth invocation: `--engine claude --claude-model opus --claude-effort high`

- `framework/scripts/ci/run_final_review.py`
  - Runs stage-specific `final-review` gate validation plus `review-evidence-link`, `drift-detection`, and `adr-index-consistency`.
  - Publishes gate result entrypoints for `final_review_gate_result`, `review_evidence_gate_result`, `drift_detection_gate_result`, and `adr_index_gate_result` in `outputs/index.json` and `outputs/run-metadata.json`.
  - Writes artifacts under `.scaffold/review_results/<scope_id>/<run_id>/final-review/`.

- `framework/scripts/ci/sync_adr_index.py`
  - Generates `docs/adr/index.json` and `docs/decisions.md` from ADR files.
  - Accepts optional `--repo-root` to resolve ADR/document paths against an explicit repository root.
  - Requires ADR body metadata (`ADR ID`, `Title`, `Status`, `Date`, `Decision`, `References/Issue`).
  - Produces deterministic, idempotent output (stable sorting and normalized values).

## Implemented validators

- `framework/scripts/gates/validate_scope_lock.py`
  - Validates `expected` vs `actual` branch and SHA identity.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `expected`, `actual`.
  - Exit code: `0` (match), `2` (mismatch or invalid input).

- `framework/scripts/gates/validate_overlap_safety.py`
  - Validates declared target-path overlap against active scopes.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `current_targets`, `active_scopes`.
  - Supports explicit waivers via `allow_overlap_with` on current/active scope objects.
  - Exit code: `0` (no overlap), `2` (overlap or invalid input).

- `framework/scripts/gates/validate_research_contract.py`
  - Validates research artifact metadata exists before PRD/Epic authoring.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `research`.
  - Exit code: `0` (valid), `2` (invalid input/mismatch).

- `framework/scripts/gates/validate_spec_quality.py`
  - Validates minimum PRD/Epic quality markers (AC and out-of-scope metadata).
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `spec`.
  - Exit code: `0` (valid), `2` (invalid input/mismatch).

- `framework/scripts/gates/validate_issue_targets.py`
  - Validates issue change targets are declared for overlap and drift checks.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `issue`.
  - Exit code: `0` (valid), `2` (invalid input/mismatch).

- `framework/scripts/gates/validate_estimate_approval.py`
  - Validates approved estimate evidence exists before implementation.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `estimate`, `approval`.
  - Exit code: `0` (approved + consistent), `2` (not approved/mismatch/invalid input).

- `framework/scripts/gates/validate_mode_selection.py`
  - Validates implementation mode selection (`impl`/`tdd`/`custom`) and rationale recording.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `estimate_approval`, `mode_selection`.
  - `custom` mode requires `custom_contract_ref`.
  - Exit code: `0` (valid), `2` (not approved/mismatch/invalid input).

- `framework/scripts/gates/validate_review_cycle.py`
  - Validates `review-cycle` evidence status and commit/range linkage.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `expected`, `review`.
  - Exit code: `0` (approved/consistent), `2` (failed/mismatch/invalid input).

- `framework/scripts/gates/validate_final_review.py`
  - Validates `final-review` evidence status and commit/range linkage.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `expected`, `review`.
  - Exit code: `0` (approved/consistent), `2` (failed/mismatch/invalid input).

- `framework/scripts/gates/validate_pr_preconditions.py`
  - Validates PR-open preconditions: scope lock + review evidence + final-review ancillary gates.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `expected`, `scope_lock`, `review_evidence`.
  - Exit code: `0` (all preconditions satisfied), `2` (missing/mismatch/invalid input).

- `framework/scripts/gates/validate_pr_bot_iteration.py`
  - Validates bot feedback iteration artifacts and resolution status normalization.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `bot_feedback`.
  - Exit code: `0` (valid), `2` (invalid input/mismatch).

- `framework/scripts/gates/validate_adr_index.py`
  - Validates ADR index entry structure, duplicate `adr_id`, indexed ADR file existence, repository-bounded ADR paths, ADR body metadata consistency, and `docs/decisions.md` table consistency.
  - Accepts optional `--repo-root` to resolve ADR/document paths against an explicit repository root.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `adr_index`.
  - Exit code: `0` (valid), `2` (invalid input/mismatch).

- `framework/scripts/gates/validate_drift_detection.py`
  - Validates declared change targets against actual changed path set (empty `actual_changes` is valid for no-diff runs, but missing declaration evidence fails).
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `declared_targets`, `actual_changes`.
  - Exit code: `0` (no undeclared drift), `2` (drift or invalid input).

- `framework/scripts/gates/validate_waiver.py`
  - Validates exception/waiver artifacts are explicit and auditable.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `waiver`.
  - Exit code: `0` (valid), `2` (invalid input).
