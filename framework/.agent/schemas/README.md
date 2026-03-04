# Schemas Layout

- `common/`: shared schema fragments used by multiple domains.
- `adapters/`: adapter input/output contracts (`review_engine`, `vcs`, `bot`).
- `gates/`: gate validator result contracts.

Keep schema references stable via repository-relative paths in `manifest.yaml`.
