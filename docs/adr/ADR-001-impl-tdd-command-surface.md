# ADR

## ADR ID
- ADR-001

## Title
Keep `/impl` and `/tdd` as separate command surfaces in v1

## Status
- accepted

## Date
- 2026-03-03

## Context

- `framework/scripts/manifest.yaml` maps both `/impl` and `/tdd` to the same must contracts:
  `estimate-approval` and `mode-selection-recorded`.
- The workflow contract describes implementation mode selection as `impl` / `tdd` / custom,
  so mode evidence is first-class and must remain explicit.
- Command-surface slimming is in progress, but the current objective is to reduce command sprawl
  without breaking existing contract semantics or user mental model.

## Decision

- Keep both `/impl` and `/tdd` in the v1 command surface (both `core`).
- Do not unify them into a single command in v1.
- Revisit consolidation only after adapter/sync rollout stabilizes and command telemetry is available.

## Consequences

### Positive
- Preserves current contract language and avoids semantic drift in existing docs.
- Keeps explicit user intent at command entry (`normal impl` vs `strict tdd`).
- Avoids migration risk while command-tier rollout (`core`/`conditional`) is still being introduced.

### Negative
- Command surface remains slightly larger than a unified interface.
- Future consolidation work is deferred, so alias/deprecation work remains pending.

## Migration Plan (Optional Future)

1. Introduce optional unified entrypoint (`/impl --mode tdd`) as alias-capable path.
2. Keep `/tdd` as backward-compatible alias during transition window.
3. Emit compatibility warning when `/tdd` is used after deprecation start.
4. Remove `/tdd` only after:
   - command usage confirms safe migration,
   - no contract/document inconsistencies remain,
   - and a replacement path is stable across Codex/Claude/OpenCode sync outputs.

## References
- Epic: `docs/epics/epic-scaffold-dev-cycle-v1.md`
- Issue: https://github.com/ToaruPen/Scaffold/issues/20
