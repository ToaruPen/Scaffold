# Hard Gates (MVP)

## Gate A: Research Before Spec

- PRD/Epic authoring requires a linked research artifact.

## Gate B: Spec Quality Minimum

- PRD/Epic must include measurable AC and explicit out-of-scope section.

## Gate C: Estimate Approval

- Implementation requires approved estimate evidence.

## Gate D: Review Evidence

- Merge path requires review evidence linked to current commit/range.
- Re-review triggers are configurable by policy YAML: `framework/config/review-evidence-policy.yaml`.

## Gate E: ADR Consistency

- ADR body, `docs/adr/index.json`, and `docs/decisions.md` must be consistent.

---

## Implementation Note

- This document defines policy-level gates.
- Contract IDs and command mappings are maintained in `framework/scripts/manifest.yaml`.
- Adapter boundaries for multi-agent execution are defined in `adapter-interfaces.md`.
