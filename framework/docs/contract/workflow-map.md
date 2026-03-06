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
6. Run review chain (`review-cycle` -> `final-review`)
7. Commit/push and create PR
8. Run PR bot feedback loop until resolved
9. Human final review and merge decision

## On-Demand Command Loading Rule

- At each step, read only the command contract required for that step.
- Do not preload all command docs.
- If a gate fails, load only related gate contract docs and retry.

## Command Tier Policy

- Command tier source of truth is `framework/scripts/manifest.yaml` (`command_tiers`).
- `core` commands are always in the default execution surface.
- `conditional` commands are enabled only when the repository explicitly opts in for that capability.
- Any command listed in `must_command_contracts` must be classified as `core` or `conditional`.
- Commands outside `command_tiers` are out of scope for Scaffold's distributable command surface.

## Required Evidence by Phase

- Requirement phase: PRD/Epic artifacts
- Planning phase: issue change targets + estimate approval
- Review phase: review-cycle/final evidence linked to commit/range
- Merge phase: PR preconditions and bot feedback cycle records
