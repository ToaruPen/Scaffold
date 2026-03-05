from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST_PATH = Path("framework/scripts/manifest.yaml")


class ManifestLoadError(ValueError):
    pass


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestLoadError(f"failed to read manifest: {exc}") from exc

    try:
        yaml_module = importlib.import_module("yaml")
    except ModuleNotFoundError as exc:
        raise ManifestLoadError("missing dependency: PyYAML") from exc

    try:
        raw = yaml_module.safe_load(text)
    except Exception as exc:
        raise ManifestLoadError(f"failed to parse manifest yaml: {exc}") from exc

    if not isinstance(raw, dict):
        raise ManifestLoadError("manifest root must be a YAML object")
    return raw


def load_default_manifest(repo_root: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    candidate = manifest_path if manifest_path is not None else DEFAULT_MANIFEST_PATH
    resolved = candidate if candidate.is_absolute() else repo_root / candidate
    return load_manifest(resolved)


def find_contract(manifest: dict[str, Any], contract_id: str) -> dict[str, Any] | None:
    contracts = manifest.get("contracts")
    if not isinstance(contracts, list):
        return None

    for contract in contracts:
        if not isinstance(contract, dict):
            continue
        current_id = contract.get("id")
        if isinstance(current_id, str) and current_id == contract_id:
            return contract
    return None


def required_contracts_for_command(manifest: dict[str, Any], command: str) -> list[str]:
    command_map = manifest.get("must_command_contracts")
    if not isinstance(command_map, dict):
        return []

    payload = command_map.get(command)
    if not isinstance(payload, dict):
        return []

    requires = payload.get("requires")
    if not isinstance(requires, list):
        return []

    values: list[str] = []
    for item in requires:
        if isinstance(item, str) and item.strip():
            values.append(item.strip())
    return values
