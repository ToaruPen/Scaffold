# AGENTS.md

Scaffold repository rules.

## Two-Layer Model

- `framework/` is the distributable product.
- `tooling/` is maintenance tooling for distribution.

## Execution Model

- Follow `framework/docs/contract/workflow-map.md` first.
- Load command details on demand for the active workflow step only.
- Avoid loading all command docs into context at once.

## Hard-Gate Philosophy

- Hard-gate artifacts/evidence, not procedural choreography.
- Fail fast when required artifacts are missing.
- Keep exceptions explicit and auditable.

## Script Governance

- All distributable validators live under `framework/scripts/gates/`.
- Shared code belongs in `framework/scripts/lib/`.
- CI entrypoints belong in `framework/scripts/ci/`.
- Script tests belong in `tests/framework/`.

## Change Discipline

- Changes under `framework/` must update contract docs or manifest when behavior changes.
- Keep validator scripts deterministic and side-effect-free.
- Avoid monolithic scripts; split at around 200 lines into `lib/` modules.
