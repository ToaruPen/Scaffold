from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from framework.scripts.lib.contract_loader import (
    ManifestLoadError,
    find_contract,
    load_default_manifest,
    load_manifest,
    required_contracts_for_command,
)


class ContractLoaderTests(unittest.TestCase):
    def test_load_manifest_reads_yaml_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.yaml"
            path.write_text(
                "\n".join(
                    [
                        "version: 2",
                        "contracts:",
                        "  - id: adr-index-consistency",
                        "must_command_contracts:",
                        "  /final-review:",
                        "    requires:",
                        "      - adr-index-consistency",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            manifest = load_manifest(path)

        self.assertEqual(manifest["version"], 2)
        self.assertEqual(manifest["contracts"][0]["id"], "adr-index-consistency")

    def test_load_manifest_fails_on_invalid_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.yaml"
            path.write_text("- not-an-object\n", encoding="utf-8")

            with self.assertRaises(ManifestLoadError):
                load_manifest(path)

    def test_load_default_manifest_uses_repo_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            manifest_path = repo_root / "framework/scripts/manifest.yaml"
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text("version: 2\n", encoding="utf-8")

            manifest = load_default_manifest(repo_root)

        self.assertEqual(manifest["version"], 2)

    def test_find_contract_returns_expected_contract(self) -> None:
        manifest = {
            "contracts": [
                {"id": "scope-lock", "validator": "a.py"},
                {"id": "adr-index-consistency", "validator": "b.py"},
            ]
        }

        contract = find_contract(manifest, "adr-index-consistency")

        self.assertIsNotNone(contract)
        assert contract is not None
        self.assertEqual(contract["validator"], "b.py")

    def test_required_contracts_for_command_returns_trimmed_values(self) -> None:
        manifest = {
            "must_command_contracts": {
                "/final-review": {"requires": [" adr-index-consistency ", "review-evidence-link"]}
            }
        }

        required = required_contracts_for_command(manifest, "/final-review")

        self.assertEqual(required, ["adr-index-consistency", "review-evidence-link"])


if __name__ == "__main__":
    unittest.main()
