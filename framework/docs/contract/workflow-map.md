# Workflow Map

This map is the primary entry point for agents and maintainers.

## Principle

- Start from flow.
- Load only the command contract needed for the current step.
- Keep evidence contracts deterministic; keep implementation procedure flexible.

## End-to-End Flow

1. Define requirements (`PRD` -> `Epic`)
2. Split into implementation issues and declare change targets
3. Create issue branch/worktree and validate overlap safety
4. Create estimate and choose implementation mode (`impl` / `tdd` / custom)
5. Implement and produce evidence
6. Run review chain (`test-review` -> `review-cycle` -> `final-review`)
7. Commit/push and create PR
8. Run PR bot feedback loop until resolved
9. Human final review and merge decision

## On-Demand Command Loading Rule

- At each step, read only the command contract required for that step.
- Do not preload all command docs.
- If a gate fails, load only related gate contract docs and retry.

## Required Evidence by Phase

- Requirement phase: PRD/Epic artifacts
- Planning phase: issue change targets + estimate approval
- Review phase: test/review/final evidence linked to commit/range
- Merge phase: PR preconditions and bot feedback cycle records
