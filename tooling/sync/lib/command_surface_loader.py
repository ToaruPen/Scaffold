from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from framework.scripts.lib.contract_loader import find_contract, load_manifest

_ALLOWED_TIERS = {"core", "conditional"}
_COMMAND_ID_PATTERN = re.compile(r"^/[A-Za-z0-9_-]+$")

# TODO(issue-28): remove Ruff suppressions ANN401, C901, PLR0912, and PLR0915
# by splitting manifest validation from catalog normalization and tightening types.


class CommandSurfaceLoadError(ValueError):
    pass


def _resolve_path(repo_root: Path, raw: str | Path) -> Path:
    root = repo_root.resolve()
    path = raw if isinstance(raw, Path) else Path(raw)
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise CommandSurfaceLoadError("manifest_path must stay within repo_root") from exc
    return resolved


def _normalize_manifest_ref(repo_root: Path, resolved_path: Path) -> str:
    root = repo_root.resolve()
    try:
        relative = resolved_path.resolve().relative_to(root)
        return relative.as_posix()
    except ValueError as exc:
        raise CommandSurfaceLoadError("manifest_path must stay within repo_root") from exc


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


def _is_valid_command_id(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if ".." in value or "\\" in value:
        return False
    return bool(_COMMAND_ID_PATTERN.fullmatch(value))


def _slug_key(command_id: str) -> str:
    return command_id.removeprefix("/").casefold()


def _raise_on_slug_collisions(command_ids: list[str], *, field_name: str) -> None:
    slug_map: dict[str, str] = {}
    duplicates: list[str] = []
    for command_id in command_ids:
        key = _slug_key(command_id)
        existing = slug_map.get(key)
        if existing is None:
            slug_map[key] = command_id
            continue
        duplicates.extend([existing, command_id])
    if duplicates:
        unique_duplicates = ", ".join(sorted(set(duplicates)))
        raise CommandSurfaceLoadError(f"{field_name} contains slug collisions: {unique_duplicates}")


def load_command_catalog(
    repo_root: Path,
    manifest_path: str | Path,
    *,
    require_metadata: bool = True,
    require_contracts: bool = True,
) -> dict[str, Any]:
    manifest_ref = manifest_path if isinstance(manifest_path, Path) else Path(manifest_path)
    resolved_manifest_path = _resolve_path(repo_root, manifest_ref)
    try:
        manifest = load_manifest(resolved_manifest_path)
    except ValueError as exc:
        raise CommandSurfaceLoadError(str(exc)) from exc

    contracts = manifest.get("contracts")
    if require_contracts and not isinstance(contracts, list):
        raise CommandSurfaceLoadError("contracts must be a list")

    must_command_contracts = _require_mapping(manifest, "must_command_contracts")
    command_tiers = _require_mapping(manifest, "command_tiers")
    if require_metadata:
        command_metadata = _require_mapping(manifest, "command_metadata")
    else:
        raw_metadata = manifest.get("command_metadata", {})
        if raw_metadata is None:
            raw_metadata = {}
        if not isinstance(raw_metadata, dict):
            raise CommandSurfaceLoadError("command_metadata must be a mapping")
        command_metadata = raw_metadata

    invalid_must_commands = sorted(
        str(command) for command in must_command_contracts if not _is_valid_command_id(command)
    )
    if invalid_must_commands:
        details = ", ".join(invalid_must_commands)
        raise CommandSurfaceLoadError(f"must_command_contracts contains invalid entries: {details}")

    invalid_tiers = sorted(
        str(command)
        for command, tier in command_tiers.items()
        if not _is_valid_command_id(command) or tier not in _ALLOWED_TIERS
    )
    if invalid_tiers:
        details = ", ".join(invalid_tiers)
        raise CommandSurfaceLoadError(f"command_tiers contains invalid entries: {details}")

    command_ids = sorted(str(command) for command in command_tiers)
    _raise_on_slug_collisions(command_ids, field_name="command_tiers")
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
        str(command) for command in command_metadata if not _is_valid_command_id(command)
    )
    if invalid_metadata_commands:
        details = ", ".join(invalid_metadata_commands)
        raise CommandSurfaceLoadError(f"command_metadata contains invalid entries: {details}")

    metadata_ids = set(command_metadata)
    _raise_on_slug_collisions(
        sorted(str(command) for command in metadata_ids), field_name="command_metadata"
    )
    if require_metadata:
        missing_metadata = sorted(
            command for command in tier_command_ids if command not in metadata_ids
        )
        if missing_metadata:
            details = ", ".join(missing_metadata)
            raise CommandSurfaceLoadError(f"command_metadata missing entries: {details}")

        extra_metadata = sorted(
            command for command in metadata_ids if command not in tier_command_ids
        )
        if extra_metadata:
            details = ", ".join(extra_metadata)
            raise CommandSurfaceLoadError(f"command_metadata contains unknown commands: {details}")

    commands: list[dict[str, Any]] = []
    tiers: dict[str, list[str]] = {"core": [], "conditional": []}

    for command_id in command_ids:
        metadata_entry = command_metadata.get(command_id, {})
        if not isinstance(metadata_entry, dict):
            raise CommandSurfaceLoadError(f"command_metadata[{command_id}] must be a mapping")

        if require_metadata:
            summary = _require_string(
                metadata_entry.get("summary"), field_name=f"{command_id}.summary"
            )
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
        else:
            summary = ""
            when_to_use = ""
            next_steps = []

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
        if require_contracts:
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
