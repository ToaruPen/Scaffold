# tooling/sync/

Recommended synchronization model: `git subtree`.

## Why subtree

- No submodule UX burden for consumer teams.
- Full files are present in consumer repos.
- Easy one-way updates from Scaffold to consumers.

## Recommended Flow

1. Create/update a split branch from `framework/` in Scaffold.
2. Consumers pull updates from that split branch into their desired prefix.

Example commands:

```bash
# In Scaffold repository
git subtree split --prefix=framework -b framework-dist

# In consumer repository (first import)
git subtree add --prefix=.scaffold <scaffold-remote> framework-dist --squash

# In consumer repository (update)
git subtree pull --prefix=.scaffold <scaffold-remote> framework-dist --squash
```

## Notes

- Use `--squash` to keep consumer history clean.
- Keep all distributable assets under `framework/` only.
- Avoid mixing local customizations directly inside `.scaffold/`; extend via overlay files.

## Agent Command Surface Sync

Use the command surface generator to produce per-agent command inventories from
`framework/scripts/manifest.yaml`.

```bash
python3 tooling/sync/generate_command_surfaces.py
```

Or via Make targets:

```bash
make command-surfaces
make command-surfaces-conditional
```

Default behavior:

- include `core` tier commands
- exclude `conditional` tier commands

Enable conditional commands explicitly:

```bash
python3 tooling/sync/generate_command_surfaces.py --enable-conditional
```

Output profiles:

- default (`core` only): `tooling/sync/generated/default/`
- with conditional (`core` + `conditional`): `tooling/sync/generated/with-conditional/`

When `--output-root` is omitted, the script chooses the profile directory
automatically (`default` without `--enable-conditional`, `with-conditional` with it).

## Markdown Command Export Sync

Use the Markdown export generator to produce CLI-readable command definitions from
the same `framework/scripts/manifest.yaml` source of truth.

Run manually:

```bash
python3 tooling/sync/generate_markdown_command_exports.py --agent all
```

Or via Make targets:

```bash
make command-exports-markdown
make command-exports-markdown-conditional
```

Default behavior:

- write OpenCode command files to `.opencode/commands/*.md`
- write Claude skills to `.claude/skills/*/SKILL.md`
- this repository opts into the conditional markdown surface, so the standard
  `make command-exports-markdown` target writes both `core` and `conditional`
  commands to the active agent surfaces via `--write-active-surfaces`

Conditional behavior:

- write preview/reference exports to `tooling/sync/generated/with-conditional/markdown/`
- preserve `Next Commands` only when the referenced command exists on the same
  generated surface
- `--enable-conditional` alone writes the conditional preview surface
- `--enable-conditional --write-active-surfaces` installs that surface into the
  live root agent directories for repositories that explicitly opt in

Generated files are deterministic and refuse to overwrite manual files unless
`--force-overwrite-existing` is passed.

When using `--output-root`, point it at a dedicated preview directory only. The
generator writes beneath that root and only manages its own generated command /
skill paths. It refuses to target the repository root, its parent, or the
filesystem root.

## Recognition Matrix And Precedence

- `Codex`
  - command execution surface is built-in to Codex CLI
  - repository-specific behavior comes from `AGENTS.md` and generated append files
  - Scaffold does not generate Codex command markdown files
- `Claude Code`
  - Scaffold exports command-aligned guidance as `.claude/skills/*/SKILL.md`
  - repository memory and standing instructions come from `CLAUDE.md`
- `OpenCode`
  - Scaffold exports command files to `.opencode/commands/*.md`
  - repository instruction precedence is `AGENTS.md` first, `CLAUDE.md` fallback compatible

The generated Markdown exports are concise contract cards, not long procedural
manuals. Their role is to bridge each CLI's recognition format back to the same
Scaffold contracts in `framework/scripts/manifest.yaml` and
`framework/docs/contract/workflow-map.md`.

For this repository, the committed root-level Markdown surfaces are the active
conditional profile. The preview tree under
`tooling/sync/generated/with-conditional/markdown/` remains available as a
regeneration snapshot for drift checks.

## Drift Detection

Generated JSON surfaces, generated append files, and generated Markdown command
exports are all covered by repository sync tests under `tests/tooling/`.
`make verify` runs those tests, and `.github/workflows/quality.yml` runs
`make verify` in CI. If a committed generated file drifts from the source
manifest or canonical rule sources, CI fails until the files are regenerated.

## Agent Rule Sync

Generate agent-specific append files from canonical rule sources.

Canonical sources:

- `docs/agent-rules/project-base.md` (project-specific base rules)
- `docs/agent-rules/development-cycle.md` (development-cycle rules)

Generated outputs:

- `Scaffold_AGENTS.append.md`
- `Scaffold_CLAUDE.append.md`

Run manually:

```bash
python3 tooling/sync/generate_agent_rules.py
```

If a non-generated append file already exists, the script fails fast instead of
overwriting it. Use `--force-overwrite-existing` only when intentional:

```bash
python3 tooling/sync/generate_agent_rules.py --force-overwrite-existing
```

Or via Make target:

```bash
make agent-rules
```

You can override output paths with `--agents-append-path` and
`--claude-append-path`.
