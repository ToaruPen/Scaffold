# Adapter Interfaces (v1)

This document defines adapter contracts for multi-agent operation.
The goal is portability across Codex CLI, Claude Code, OpenCode, and future providers.

## Design Rules

- Keep adapter contracts small, typed, and audit-friendly.
- Keep provider-specific fields inside `provider_metadata` only.
- Return normalized status and findings regardless of provider.

## Common Envelope

All adapter operations MUST include:

- `request_id`: unique request id
- `scope_id`: issue/pr/scope identifier
- `run_id`: execution id for artifact linkage

All adapter errors MUST include:

- `code`: stable machine-readable code
- `message`: human-readable explanation
- `retryable`: whether retry is safe
- `provider`: adapter/provider identifier

Standard error codes:

- `E_INPUT_INVALID`
- `E_SCOPE_LOCK_FAILED`
- `E_ADAPTER_UNAVAILABLE`
- `E_PROVIDER_FAILURE`
- `E_TIMEOUT`
- `E_RATE_LIMIT`
- `E_AUTH`

## Review Engine Adapter

Purpose: run structured review and return normalized findings.

Operation:

- `run_review(request) -> ReviewEngineResult`

Required input fields:

- `request_id`, `scope_id`, `run_id`
- `diff_mode` (`range|staged|worktree|auto`)
- `head_sha`
- `base_sha` (optional when `diff_mode != range`)
- `review_goal` (short text describing what this review run must validate)
- `schema_version` (currently `1`)

Required output fields:

- `status` (`approved|approved_with_nits|needs_changes|blocked|question`)
- `findings[]` (normalized)
- `summary`
- `evidence` (`head_sha`, `base_sha`, `artifact_path`, `created_at`)
- `provider_metadata`

Schema:

- `framework/.agent/schemas/adapters/review-engine-result.schema.json`

## VCS Adapter

Purpose: provide scope lock checks and PR lifecycle operations.

Operations:

- `resolve_scope(scope_id) -> ScopeLockResult`
- `check_overlap(scope_id) -> OverlapSafetyResult`
- `create_or_update_pr(request) -> PrResult`
- `list_linked_branches(issue_id) -> BranchList`

`ScopeLockResult` required fields:

- `matched` (`true|false`)
- `current_branch`
- `expected_branch` (optional)
- `head_sha`
- `base_sha` (optional)
- `mismatch_reasons[]`

Schema:

- `framework/.agent/schemas/gates/vcs-scope-lock-result.schema.json`
- `framework/.agent/schemas/gates/overlap-safety-result.schema.json`

## Bot Adapter

Purpose: normalize review bot interactions and feedback loops.

Operations:

- `request_review(request) -> BotRequestResult`
- `fetch_feedback(request) -> BotFeedbackBatch`
- `mark_addressed(request) -> BotAcknowledgeResult`

`BotFeedbackBatch` required fields:

- `provider`
- `pr_number`
- `cycle`
- `status` (`no_findings|findings_present|provider_error`)
- `findings[]` (normalized)

Normalized finding required fields:

- `finding_id`
- `severity` (`P0|P1|P2|P3`)
- `title`
- `detail`
- `path` (required)
- `start_line`, `end_line` (required)
- `snippet` (required, short code excerpt matching the cited range)
- `fingerprint`

Schema:

- `framework/.agent/schemas/adapters/bot-feedback-batch.schema.json`

## Evidence and Traceability

Each adapter response MUST be linkable to:

- issue or PR scope (`scope_id`)
- source commit/range (`head_sha` / `base_sha`)
- local or CI artifact path

This keeps adapter behavior aligned with hard-gate evidence contracts.

## Stub Implementations (v1)

Minimum deterministic stubs for local/CI contract testing:

- `framework/scripts/lib/review_engine_stub.py`
- `framework/scripts/lib/vcs_stub.py`
- `framework/scripts/lib/bot_stub.py`
