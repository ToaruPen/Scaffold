# framework/scripts/

Distributable script layer for consumer repositories.

## Subdirectories

- `framework/scripts/gates/`: deterministic pass/fail validators
- `framework/scripts/lint/`: schema/template/static checks
- `framework/scripts/ci/`: CI entrypoint orchestration
- `framework/scripts/hooks/`: local git hook wrappers
- `framework/scripts/lib/`: shared helper code

## Rules

- Keep validators deterministic and side-effect free.
- One validator per artifact contract.
- Do not put policy prose in validator scripts.
- Add matching tests under `tests/framework/` for every behavior change.

## Adapter Stubs

- `framework/scripts/lib/review_engine_stub.py`
- `framework/scripts/lib/vcs_stub.py`
- `framework/scripts/lib/bot_stub.py`

## Review runner

- `framework/scripts/ci/run_review_engine.py`
  - Runs `codex` or `claude` in read-only review mode.
  - Creates artifacts under `.scaffold/review_results/<scope_id>/<run_id>/`.
  - Saves normalized review JSON and gate outputs (`review-cycle`, `review-evidence`).
  - Uses prompt template: `framework/config/review-engine-prompt.json`.

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

- `framework/scripts/gates/validate_estimate_approval.py`
  - Validates approved estimate evidence exists before implementation.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `estimate`, `approval`.
  - Exit code: `0` (approved + consistent), `2` (not approved/mismatch/invalid input).

- `framework/scripts/gates/validate_mode_selection.py`
  - Validates implementation mode selection (`impl`/`tdd`/`custom`) and rationale recording.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `estimate_approval`, `mode_selection`.
  - `custom` mode requires `custom_contract_ref`.
  - Exit code: `0` (valid), `2` (not approved/mismatch/invalid input).

- `framework/scripts/gates/validate_test_review.py`
  - Validates `test-review` evidence status and commit/range linkage.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `expected`, `review`.
  - Exit code: `0` (approved/consistent), `2` (failed/mismatch/invalid input).

- `framework/scripts/gates/validate_review_cycle.py`
  - Validates `review-cycle` evidence status and commit/range linkage.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `expected`, `review`.
  - Exit code: `0` (approved/consistent), `2` (failed/mismatch/invalid input).

- `framework/scripts/gates/validate_final_review.py`
  - Validates `final-review` evidence status and commit/range linkage.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `expected`, `review`.
  - Exit code: `0` (approved/consistent), `2` (failed/mismatch/invalid input).

- `framework/scripts/gates/validate_pr_preconditions.py`
  - Validates PR-open preconditions: scope lock + review evidence + commit/range consistency.
  - Required top-level inputs: `request_id`, `scope_id`, `run_id`, `artifact_path`, `expected`, `scope_lock`, `review_evidence`.
  - Exit code: `0` (all preconditions satisfied), `2` (missing/mismatch/invalid input).
