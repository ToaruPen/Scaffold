from __future__ import annotations

from pathlib import Path
from typing import Any

from framework.scripts.lib.contract_loader import find_contract, load_manifest

_ALLOWED_TIERS = {"core", "conditional"}


class CommandSurfaceLoadError(ValueError):
    pass


def _resolve_path(repo_root: Path, raw: str | Path) -> Path:
    path = raw if isinstance(raw, Path) else Path(raw)
    if path.is_absolute():
        return path
    return repo_root / path


def _normalize_manifest_ref(repo_root: Path, resolved_path: Path) -> str:
    try:
        relative = resolved_path.relative_to(repo_root)
        return str(relative)
    except ValueError:
        return resolved_path.name


def _require_mapping(parent: dict[str, Any], key: str) -> dict[str, Any]:
    value = parent.get(key)
    if not isinstance(value, dict):
        raise CommandSurfaceLoadError(f"{key} must be a mapping")
    return value


def _require_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CommandSurfaceLoadError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_string_list(value: Any, *, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise CommandSurfaceLoadError(f"{field_name} must be a list")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = _require_string(item, field_name=field_name)
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def load_command_catalog(repo_root: Path, manifest_path: str | Path) -> dict[str, Any]:
    manifest_ref = manifest_path if isinstance(manifest_path, Path) else Path(manifest_path)
    resolved_manifest_path = _resolve_path(repo_root, manifest_ref)
    try:
        manifest = load_manifest(resolved_manifest_path)
    except ValueError as exc:
        raise CommandSurfaceLoadError(str(exc)) from exc

    contracts = manifest.get("contracts")
    if not isinstance(contracts, list):
        raise CommandSurfaceLoadError("contracts must be a list")

    must_command_contracts = _require_mapping(manifest, "must_command_contracts")
    command_tiers = _require_mapping(manifest, "command_tiers")
    command_metadata = _require_mapping(manifest, "command_metadata")

    invalid_must_commands = sorted(
        str(command) for command in must_command_contracts if not isinstance(command, str)
    )
    if invalid_must_commands:
        details = ", ".join(invalid_must_commands)
        raise CommandSurfaceLoadError(f"must_command_contracts contains invalid entries: {details}")

    invalid_tiers = sorted(
        str(command)
        for command, tier in command_tiers.items()
        if not isinstance(command, str) or tier not in _ALLOWED_TIERS
    )
    if invalid_tiers:
        details = ", ".join(invalid_tiers)
        raise CommandSurfaceLoadError(f"command_tiers contains invalid entries: {details}")

    command_ids = sorted(str(command) for command in command_tiers)
    must_command_ids = set(must_command_contracts)
    tier_command_ids = set(command_ids)

    missing_tiers = sorted(
        command for command in must_command_ids if command not in tier_command_ids
    )
    if missing_tiers:
        details = ", ".join(missing_tiers)
        raise CommandSurfaceLoadError(
            f"must_command_contracts missing tier classification: {details}"
        )

    invalid_metadata_commands = sorted(
        str(command) for command in command_metadata if not isinstance(command, str)
    )
    if invalid_metadata_commands:
        details = ", ".join(invalid_metadata_commands)
        raise CommandSurfaceLoadError(f"command_metadata contains invalid entries: {details}")

    metadata_ids = set(command_metadata)
    missing_metadata = sorted(
        command for command in tier_command_ids if command not in metadata_ids
    )
    if missing_metadata:
        details = ", ".join(missing_metadata)
        raise CommandSurfaceLoadError(f"command_metadata missing entries: {details}")

    extra_metadata = sorted(command for command in metadata_ids if command not in tier_command_ids)
    if extra_metadata:
        details = ", ".join(extra_metadata)
        raise CommandSurfaceLoadError(f"command_metadata contains unknown commands: {details}")

    commands: list[dict[str, Any]] = []
    tiers = {"core": [], "conditional": []}

    for command_id in command_ids:
        metadata_entry = command_metadata.get(command_id)
        if not isinstance(metadata_entry, dict):
            raise CommandSurfaceLoadError(f"command_metadata[{command_id}] must be a mapping")

        summary = _require_string(metadata_entry.get("summary"), field_name=f"{command_id}.summary")
        when_to_use = _require_string(
            metadata_entry.get("when_to_use"), field_name=f"{command_id}.when_to_use"
        )
        next_steps = _require_string_list(
            metadata_entry.get("next_steps"), field_name=f"{command_id}.next_steps"
        )

        invalid_next_steps = sorted(step for step in next_steps if step not in tier_command_ids)
        if invalid_next_steps:
            details = ", ".join(invalid_next_steps)
            raise CommandSurfaceLoadError(
                f"{command_id}.next_steps contains unknown commands: {details}"
            )

        required_contract_ids: list[str] = []
        command_payload = must_command_contracts.get(command_id)
        if command_payload is not None:
            if not isinstance(command_payload, dict):
                raise CommandSurfaceLoadError(
                    f"must_command_contracts[{command_id}] must be a mapping"
                )
            required_contract_ids = _require_string_list(
                command_payload.get("requires", []), field_name=f"{command_id}.requires"
            )

        required_contracts: list[dict[str, str]] = []
        for contract_id in required_contract_ids:
            contract = find_contract(manifest, contract_id)
            if contract is None:
                raise CommandSurfaceLoadError(
                    f"{command_id} requires unknown contract: {contract_id}"
                )
            description = _require_string(
                contract.get("description"), field_name=f"contract {contract_id} description"
            )
            validator = _require_string(
                contract.get("validator"), field_name=f"contract {contract_id} validator"
            )
            required_contracts.append(
                {
                    "id": contract_id,
                    "description": description,
                    "validator": validator,
                }
            )

        tier = command_tiers[command_id]
        command_info = {
            "id": command_id,
            "slug": command_id.removeprefix("/"),
            "tier": tier,
            "summary": summary,
            "when_to_use": when_to_use,
            "next_steps": next_steps,
            "required_contracts": required_contracts,
        }
        commands.append(command_info)
        tiers[tier].append(command_id)

    return {
        "manifest_path": _normalize_manifest_ref(repo_root, resolved_manifest_path),
        "commands": commands,
        "tiers": tiers,
    }
