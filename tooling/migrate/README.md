# tooling/migrate/

Migration helper for analyzing existing repositories before adopting Scaffold.

Use this command to scan a target repository and produce a read-only migration
readiness report.

## CLI

Usage:

```bash
python3 tooling/migrate/migrate_helper.py --target-repo /path/to/repo [options]
```

Options:

- `--target-repo PATH` (required): path to the target repository to analyze
- `--scaffold-repo PATH` (default: current directory): path to the Scaffold source
- `--output PATH`: write report to a file instead of stdout
- `--format {text}` (default: `text`): output format

## Examples

```bash
# Analyze target repo (output to stdout)
python3 tooling/migrate/migrate_helper.py --target-repo /path/to/repo

# Save report to file
python3 tooling/migrate/migrate_helper.py --target-repo /path/to/repo --output report.txt
```

## Report format

The report includes these sections:

- `Summary`
- `File Mappings`
- `Conflicts`
- `Required Manual Fixes`

## Note

This tool is read-only. It only analyzes the target repository and does not
perform writes to it.
