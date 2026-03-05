# ADR Operations Contract

## Purpose

Define deterministic ADR maintenance rules for `docs/adr/index.json` and `docs/decisions.md`.

## Source of Truth

- ADR body files under `docs/adr/ADR-*.md` are the source of truth.
- `docs/adr/index.json` is a generated machine index.
- `docs/decisions.md` is a generated human index.

## Required ADR Sections

- `## ADR ID`
- `## Title`
- `## Status`
- `## Date`
- `## Context`
- `## Decision`
- `## Consequences`
- `## References` with `Issue:` value

## Sync Procedure

1. Update ADR body files.
2. Run `python3 framework/scripts/ci/sync_adr_index.py`.
3. Validate with `python3 framework/scripts/gates/validate_adr_index.py --input <input.json> --output <output.json>` through the normal final-review flow.

## Supersede Rules

- A superseding ADR sets `Status` to `accepted` (or project-approved final state).
- The superseded ADR sets `Status` to `superseded`.
- The superseding ADR should include `## Supersedes (Optional)` with one or more `ADR-XXXX` references.
- `sync_adr_index.py` exports `supersedes` into `docs/adr/index.json` when present.
- `docs/decisions.md` remains generated from ADR bodies and must not be hand-edited.
