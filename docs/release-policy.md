# Release Policy

This document describes how Scaffold is versioned, what stability guarantees consumers can rely on, and how to stay current with updates.

## Versioning

Scaffold follows [Semantic Versioning](https://semver.org/).

- **v0.x releases** — initial development phase. Breaking changes may occur in any release without a deprecation cycle.
- **v1.0+** (future) — production-ready. Breaking changes will be preceded by deprecation notices and a transition window.

## Compatibility Scope

Not all parts of the repository carry the same stability guarantee.

**In scope** (v1.0+ only) — stable across minor versions within the same major:

- `framework/docs/contract/` — workflow contracts
- `framework/scripts/manifest.yaml` — gate manifest schema
- `framework/scripts/gates/` — gate script interfaces

**Out of scope** — may change without notice:

- `tooling/` internals
- `docs/` (repository-level docs, not contract docs)
- Generated files (command surfaces, agent rules)

> **Note**: During the v0.x phase, all parts of the repository may change without notice.

## Consumer Update Guidelines

- Sync updates using `git subtree pull` (see [tooling/sync/README.md](../tooling/sync/README.md) for commands).
- Review release notes before pulling an update.
- Pin to a specific tag and update intentionally rather than tracking a branch.
- Run `make verify` after each update to catch breaking changes early.

## Release Notes Format

Each release includes a changelog following [keepachangelog.com](https://keepachangelog.com/) conventions:

- **Added** — new features or capabilities
- **Changed** — modifications to existing behavior
- **Fixed** — bug fixes
- **Breaking** — changes that require consumer action

## Tagging Convention

- Tags follow `vMAJOR.MINOR.PATCH` format.
- Pre-release: `v0.x.y` — initial development phase.
- Stable: `v1.0.0+` — production-ready (future).
