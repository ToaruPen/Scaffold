# Gate Operations

Operational guide for running and troubleshooting Scaffold gate validators.

## Prerequisites

- Python 3.11+
- Dependencies installed: `python3 -m pip install -r framework/requirements-dev.txt`
- Repository root as current working directory

## Core Commands

- Full quality check: `make verify`
- Unit tests only: `python3 -m unittest discover -s tests/framework -p "test_*.py"`
- Schema check only: `check-jsonschema --schemafile https://json-schema.org/draft/2020-12/schema framework/.agent/schemas/*/*.json`

## Contract Inventory

The source of truth is `framework/scripts/manifest.yaml`.

- Contract definitions: `contracts:`
- Command mapping: `must_command_contracts:`
- Adapter boundaries: `adapter_interfaces:`

## Validator Execution Pattern

All validators follow the same CLI shape:

```bash
python3 framework/scripts/gates/validate_<name>.py --input <input.json> --output <result.json>
```

Exit codes:

- `0`: pass
- `2`: fail or invalid input

## Review Chain Operations

Review chain stages:

1. test-review
2. review-cycle
3. final-review

Runners:

- `framework/scripts/ci/run_test_review.py`
- `framework/scripts/ci/run_review_engine.py`
- `framework/scripts/ci/run_final_review.py`

Each runner writes artifacts under `.scaffold/review_results/<scope_id>/<run_id>/...`.

## Waiver Operations

Use waiver template:

- `framework/templates/waiver/template.json`

Validate a waiver artifact:

```bash
python3 framework/scripts/gates/validate_waiver.py --input <waiver.json> --output <waiver.result.json>
```

Waiver records are evidence artifacts. They do not bypass other validators by default.

## CI Workflows

Scaffold repository:

- `.github/workflows/quality.yml`
- `.github/workflows/gates.yml`

Consumer sample workflow:

- `framework/.github/workflows/scaffold-gates.yml`

## Troubleshooting

### `check-jsonschema: command not found`

Install dependencies:

```bash
python3 -m pip install -r framework/requirements-dev.txt
```

### Gate returns `E_INPUT_INVALID`

- Validate input JSON structure against the expected contract.
- Compare with existing tests in `tests/framework/` for minimal valid payloads.

### Schema validation fails

- Validate schema syntax with draft-2020-12 schema.
- Confirm `$ref` paths use repository-relative stable paths.

### Review runner fails resolving sha

- Ensure the repository has commits.
- Ensure `--base-ref` exists locally (for example `origin/main`).

## Release Checklist

- `make verify` passes
- All manifest contracts are `status: implemented`
- New validators have matching tests and schemas
- CI workflows parse correctly and run in PR context
