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
