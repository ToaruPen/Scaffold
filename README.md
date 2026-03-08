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

## Quick Start

Adopt Scaffold into an existing repository in about 5-10 minutes. You need Python 3.11+ and git.

1. **Clone Scaffold** (or add it as a remote in an existing clone):

   ```bash
   git clone <scaffold-repository-url>
   cd Scaffold
   ```

2. **Run preflight check** to verify compatibility before touching your repo:

   ```bash
   python3 tooling/install/install_helper.py --target-repo /path/to/your-repo --dry-run
   ```

3. **Execute installation** once preflight passes:

   ```bash
   python3 tooling/install/install_helper.py --target-repo /path/to/your-repo --execute
   ```

4. **Verify the setup** inside your consumer repo:

   ```bash
   cd /path/to/your-repo
   ls .scaffold/                  # confirm framework payload is present
   cat .scaffold/scripts/manifest.yaml  # confirm gate manifest exists
   ```

   Note: only `framework/` is synced via `git subtree add`. The consumer repo must provide its own `Makefile` or run the framework-provided gate scripts directly.

That's it. Your repo now has the `framework/` payload synced under `.scaffold/` and the gate contracts in place.

## Adoption Guide

Three paths exist depending on how much tooling you want.

### Minimal adoption (subtree only)

Use `git subtree` directly if you prefer no helper scripts. Three commands get you running:

```bash
# In Scaffold: create a stable distribution branch
git subtree split --prefix=framework -b framework-dist

# In your repo: add Scaffold as a subtree (first time)
git subtree add --prefix=.scaffold <scaffold-remote> framework-dist --squash

# In your repo: pull updates later
git subtree pull --prefix=.scaffold <scaffold-remote> framework-dist --squash
```

This gives you the `framework/` payload with no dependency on Scaffold's tooling internals. See [tooling/sync/README.md](tooling/sync/README.md) for full sync details.

### Full adoption with tooling

Use `install_helper.py` when you want automated preflight checks, conflict detection, and a dry-run preview before committing changes. The helper validates your environment, checks for path conflicts, and applies the subtree in one step. See [tooling/install/README.md](tooling/install/README.md) for all flags and options.

### Migration from an existing setup

If your repo already has a partial or conflicting Scaffold layout, run `migrate_helper.py` first. It analyzes your current state and reports conflicts before any files change. Once the report is clean, proceed with the install path above. See [tooling/migrate/README.md](tooling/migrate/README.md) for usage.

## Release Policy

See [docs/release-policy.md](docs/release-policy.md) for versioning, compatibility scope, and update guidelines.

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

## License

Scaffold is distributed under the MIT License. You may freely use, modify, and redistribute it in your projects. See `LICENSE` for details.

Reuse policy: vendor/subtree sync is the recommended adoption method.

- You may vendor or subtree-sync the repository into downstream projects.
- Modifications are allowed under the same license terms.
- Redistribution is allowed, including in third-party projects.
- Keep the copyright notice and permission text intact in copied/reused artifacts.
