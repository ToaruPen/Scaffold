# Scaffold

Scaffold is a source repository for a reusable AI-assisted development framework.

## Design Intent

- Keep hard gates only for artifacts and evidence.
- Keep implementation procedures flexible.
- Make distribution to other repositories explicit and maintainable.

## Repository Layout

```text
.
|- framework/        # distributable payload for target repositories
|- tooling/          # install/sync/migrate helpers for framework rollout
|- tests/            # framework + tooling validation
`- docs/             # Scaffold repository docs and decisions
```

## Operating Model

- Start from the workflow map: `framework/docs/contract/workflow-map.md`
- Read only the command contract needed for the current step
- Keep command docs as on-demand references, not always-loaded context

## Distribution Rule

- Treat `framework/` as the only sync payload.
- Do not couple consumer repositories to `tooling/` internals.
- Keep gate contracts in `framework/scripts/manifest.yaml`.

## Recommended Sync Strategy

- Use `git subtree` for existing repositories (simple operations, no submodule UX cost).
- Use a split branch from `framework/` as the stable upstream for consumers.

## Quality Baseline

- Install dev tools into `.venv`: `make install-dev`
- Run full checks from `.venv/bin`: `make verify`
- Optional local hook flow: `pre-commit install` then `make pre-commit`
- Commit message lint hook: `pre-commit install --hook-type commit-msg`
- Quick commitlint smoke test: `make commitlint-check`
- CI commit range lint: `make commitlint-range FROM=<base_sha> TO=<head_sha>`

Current baseline checks:

- Lint: `ruff check`
- Shell lint: `shellcheck`
- Ruff rule groups: `E,F,I,W,B,PLE,UP,RUF,C4,C90,SIM,PLC,PLW,ANN,PLR`
- McCabe complexity limit: `max-complexity = 10`
- Format: `ruff format --check`
- Typecheck: `mypy`
- Schema validation: `check-jsonschema`
- Commit messages: `commitlint` (pre-commit `commit-msg` stage)
- Unit tests: `python3 -m unittest`

CI workflow:

- `.github/workflows/quality.yml` runs `make verify` on push/PR.
- The same workflow runs commitlint on commit ranges (PR base/head or push before/after).
