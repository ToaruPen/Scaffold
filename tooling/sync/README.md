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
