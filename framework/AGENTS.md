# AGENTS.md (Scaffold Framework)

This file is intended to be synchronized into consumer repositories.

## Core Policy

- Enforce artifact/evidence contracts.
- Do not enforce a rigid step-by-step implementation procedure.
- Fail fast on missing required evidence.

## Hard Gate Targets (MVP)

1. Research artifact exists before PRD/Epic authoring.
2. PRD/Epic have measurable acceptance criteria and out-of-scope section.
3. Estimate approval artifact exists before implementation.
4. Review evidence artifact links to current commit/range.
5. ADR index and ADR body remain consistent.

## Script Structure

- `framework/scripts/gates/`: deterministic validators
- `framework/scripts/lib/`: shared utility code
- `framework/scripts/ci/`: CI orchestration wrappers
