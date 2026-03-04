.PHONY: install-dev lint format format-check typecheck schema-check test verify pre-commit commitlint-check commitlint-range command-surfaces command-surfaces-conditional

install-dev:
	python3 -m pip install -r requirements-dev.txt

lint:
	ruff check framework tests

format:
	ruff format framework tests

format-check:
	ruff format --check framework tests

typecheck:
	mypy --config-file pyproject.toml

schema-check:
	check-jsonschema --schemafile https://json-schema.org/draft/2020-12/schema framework/.agent/schemas/*/*.json

test:
	python3 -m unittest discover -s tests/framework -p "test_*.py"
	python3 -m unittest discover -s tests/tooling -p "test_*.py"

verify: lint format-check typecheck schema-check test

command-surfaces:
	python3 tooling/sync/generate_command_surfaces.py --output-root tooling/sync/generated/default --agent all

command-surfaces-conditional:
	python3 tooling/sync/generate_command_surfaces.py --output-root tooling/sync/generated/with-conditional --agent all --enable-conditional

pre-commit:
	pre-commit run --all-files

commitlint-check:
	printf "feat: scaffold quality baseline\n" | npx --yes -p @commitlint/cli -p @commitlint/config-conventional commitlint --config commitlint.config.cjs

commitlint-range:
	@if [ -z "$(FROM)" ] || [ -z "$(TO)" ]; then echo "FROM and TO are required"; exit 2; fi
	npx --yes -p @commitlint/cli -p @commitlint/config-conventional commitlint --config commitlint.config.cjs --from "$(FROM)" --to "$(TO)" --verbose
