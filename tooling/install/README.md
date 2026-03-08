# tooling/install/

Install helper for bootstrapping `framework/` into a target repository.

Use this command when you want to adopt Scaffold in a clean repository by
installing `framework/` into a git prefix using `git subtree add`.

## Prerequisites

- `git` in PATH
- Python 3.11+

## CLI

Usage:

```bash
python3 tooling/install/install_helper.py --target-repo /path/to/repo [options]
```

Options:

- `--target-repo PATH` (required): path to the target repository
- `--scaffold-repo PATH` (default: current directory): path to the Scaffold source
- `--prefix PREFIX` (default: `.scaffold`): subtree destination prefix
- `--dry-run`: print the installation plan without changes
- `--execute`: perform `git subtree add`

Safety note: dry-run is the default mode. Omit `--execute` and no files are
written.

## Examples

```bash
# Dry run (preview only)
python3 tooling/install/install_helper.py --target-repo /path/to/repo --dry-run

# Execute installation
python3 tooling/install/install_helper.py --target-repo /path/to/repo --execute
```

## Preflight checks

- `is_git_repo` — target path is a git worktree
- `no_existing_scaffold` — `.scaffold` and `framework` are absent
- `clean_working_tree` — no uncommitted changes in target repository
