.PHONY: all clean install-dev lint lint-shell format format-check typecheck schema-check test verify pre-commit commitlint-check commitlint-range command-surfaces command-surfaces-conditional command-exports-markdown command-exports-markdown-conditional agent-rules

VENV_DIR ?= .venv
VENV_BIN ?= $(VENV_DIR)/bin
PYTHON ?= $(VENV_BIN)/python
RUFF ?= $(VENV_BIN)/ruff
MYPY ?= $(VENV_BIN)/mypy
CHECK_JSONSCHEMA ?= $(VENV_BIN)/check-jsonschema
PRE_COMMIT ?= $(VENV_BIN)/pre-commit
SHELLCHECK ?= $(VENV_BIN)/shellcheck
SHELL_FILES = $(shell find framework -type f -name '*.sh' | sort)

export PATH := $(abspath $(VENV_BIN)):$(PATH)

all: verify

clean:
	rm -rf build dist .mypy_cache .pytest_cache .ruff_cache .coverage .scaffold/review_results
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

install-dev:
	@if [ ! -d "$(VENV_DIR)" ]; then python3 -m venv "$(VENV_DIR)"; fi
	$(PYTHON) -m pip install -r requirements-dev.txt

lint:
	$(RUFF) check framework tests

lint-shell:
	@if [ -n "$(strip $(SHELL_FILES))" ]; then \
		$(SHELLCHECK) $(SHELL_FILES); \
	else \
		echo "No shell files found under framework; skipping shellcheck."; \
	fi

format:
	$(RUFF) format framework tests

format-check:
	$(RUFF) format --check framework tests

typecheck:
	$(MYPY) --config-file pyproject.toml

schema-check:
	$(CHECK_JSONSCHEMA) --schemafile https://json-schema.org/draft/2020-12/schema framework/.agent/schemas/*/*.json

test:
	$(PYTHON) -m unittest discover -s tests/framework -p "test_*.py"
	$(PYTHON) -m unittest discover -s tests/tooling -p "test_*.py"

verify: lint lint-shell format-check typecheck schema-check test

command-surfaces:
	$(PYTHON) tooling/sync/generate_command_surfaces.py --output-root tooling/sync/generated/default --agent all

command-surfaces-conditional:
	$(PYTHON) tooling/sync/generate_command_surfaces.py --output-root tooling/sync/generated/with-conditional --agent all --enable-conditional

command-exports-markdown:
	$(PYTHON) tooling/sync/generate_markdown_command_exports.py --agent all

command-exports-markdown-conditional:
	$(PYTHON) tooling/sync/generate_markdown_command_exports.py --agent all --enable-conditional

agent-rules:
	$(PYTHON) tooling/sync/generate_agent_rules.py

pre-commit:
	$(PRE_COMMIT) run --all-files

commitlint-check:
	printf "feat: scaffold quality baseline\n" | npx --yes -p @commitlint/cli -p @commitlint/config-conventional commitlint --config commitlint.config.cjs

commitlint-range:
	@if [ -z "$(FROM)" ] || [ -z "$(TO)" ]; then echo "FROM and TO are required"; exit 2; fi
	npx --yes -p @commitlint/cli -p @commitlint/config-conventional commitlint --config commitlint.config.cjs --from "$(FROM)" --to "$(TO)" --verbose
