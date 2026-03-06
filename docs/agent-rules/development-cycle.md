## Development Cycle Rules

Keep the development cycle concise, explicit, and evidence-driven.

- Start from `framework/docs/contract/workflow-map.md`.
- Load only the command contract needed for the active step.
- Use this canonical path unless explicitly waived:
  - `issue` -> `estimation` -> `impl/tdd/custom` -> `review-cycle` -> `final-review` -> `create-pr`.

### Evidence And Gates

- Treat gate outputs as required artifacts, not optional notes.
- Fail fast when required evidence is missing or stale.
- Do not bypass hard gates with procedural shortcuts.
- Keep exception handling explicit, time-bounded, and auditable.

### Review Loop

- Apply bot findings, re-run verification, and request re-review.
- Resolve only findings that are actually addressed in code.
- Keep changes minimal and scoped to the active issue.

### Operational Discipline

- Verify with deterministic commands (`make verify` for repo-level checks).
- Keep instructions short and specific; remove ambiguous guidance.
- Avoid conflicting rules across nested instruction files.
