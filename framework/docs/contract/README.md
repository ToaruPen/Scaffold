# Framework Contracts

This directory defines hard gate contracts distributed to consumer repositories.

## Contract Scope

- Required artifacts and evidence
- Validator ownership and locations
- Exception handling expectations
- Adapter interface contracts (`review_engine`, `vcs`, `bot`)
- Command-to-contract mapping source (`framework/scripts/manifest.yaml`)

## Primary Documents

- `hard-gates.md`: policy-level gate requirements
- `adapter-interfaces.md`: adapter I/F contracts
- `workflow-map.md`: flow-first operation and on-demand command loading
- `framework/scripts/manifest.yaml`: executable contract inventory and command mapping

## Not in Contract Scope

- Exact command choreography
- Prompt templates and role wording
- Agent assignment strategy
