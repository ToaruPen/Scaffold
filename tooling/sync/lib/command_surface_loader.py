from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, NamedTuple, TypedDict, cast

from framework.scripts.lib.contract_loader import find_contract, load_manifest

CommandTier = Literal["core", "conditional"]
ManifestMapping = Mapping[str, object]
RawMapping = Mapping[object, object]

_ALLOWED_TIERS: tuple[CommandTier, ...] = ("core", "conditional")
_COMMAND_ID_PATTERN = re.compile(r"^/[A-Za-z0-9_-]+$")
_WINDOWS_RESERVED_NAMES = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{index}" for index in range(1, 10)),
    *(f"lpt{index}" for index in range(1, 10)),
}


class RequiredContractInfo(TypedDict):
    id: str
    description: str
    validator: str


class CommandCatalogEntry(TypedDict):
    id: str
    slug: str
    tier: CommandTier
    summary: str
    when_to_use: str
    next_steps: list[str]
    required_contracts: list[RequiredContractInfo]


class CommandCatalog(TypedDict):
    manifest_path: str
    commands: list[CommandCatalogEntry]
    tiers: dict[CommandTier, list[str]]


class CatalogSections(NamedTuple):
    must_command_contracts: RawMapping
    command_tiers: dict[str, CommandTier]
    command_metadata: RawMapping


class CatalogBuildContext(NamedTuple):
    manifest: dict[str, object]
    sections: CatalogSections
    require_metadata: bool
    require_contracts: bool
    command_ids: set[str]


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


def _require_mapping(parent: ManifestMapping, key: str) -> RawMapping:
    value = parent.get(key)
    if not isinstance(value, Mapping):
        raise CommandSurfaceLoadError(f"{key} must be a mapping")
    return value


def _optional_mapping(parent: ManifestMapping, key: str) -> RawMapping:
    value = parent.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise CommandSurfaceLoadError(f"{key} must be a mapping")
    return value


def _require_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CommandSurfaceLoadError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_string_list(value: object, *, field_name: str) -> list[str]:
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
    if not _COMMAND_ID_PATTERN.fullmatch(value):
        return False
    slug = _slug_key(value)
    first_segment = slug.split("/", 1)[0]
    base_name = first_segment.split(".", 1)[0]
    return base_name not in _WINDOWS_RESERVED_NAMES


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


def _load_manifest_payload(
    repo_root: Path, manifest_path: str | Path
) -> tuple[dict[str, object], Path]:
    manifest_ref = manifest_path if isinstance(manifest_path, Path) else Path(manifest_path)
    resolved_manifest_path = _resolve_path(repo_root, manifest_ref)
    try:
        manifest = cast(dict[str, object], load_manifest(resolved_manifest_path))
    except ValueError as exc:
        raise CommandSurfaceLoadError(str(exc)) from exc
    return manifest, resolved_manifest_path


def _require_contract_section(manifest: dict[str, object], *, require_contracts: bool) -> None:
    contracts = manifest.get("contracts")
    if require_contracts and not isinstance(contracts, list):
        raise CommandSurfaceLoadError("contracts must be a list")


def _normalize_command_tiers(command_tiers: RawMapping) -> dict[str, CommandTier]:
    invalid_tiers = sorted(
        str(command)
        for command, tier in command_tiers.items()
        if not _is_valid_command_id(command) or tier not in _ALLOWED_TIERS
    )
    if invalid_tiers:
        details = ", ".join(invalid_tiers)
        raise CommandSurfaceLoadError(f"command_tiers contains invalid entries: {details}")
    return {str(command): cast(CommandTier, tier) for command, tier in command_tiers.items()}


def _raise_on_invalid_command_ids(section: RawMapping, *, field_name: str) -> None:
    invalid_ids = sorted(str(command) for command in section if not _is_valid_command_id(command))
    if invalid_ids:
        details = ", ".join(invalid_ids)
        raise CommandSurfaceLoadError(f"{field_name} contains invalid entries: {details}")


def _validate_command_ids(section: RawMapping, *, field_name: str) -> list[str]:
    _raise_on_invalid_command_ids(section, field_name=field_name)
    command_ids = sorted(str(command) for command in section)
    _raise_on_slug_collisions(command_ids, field_name=field_name)
    return command_ids


def _load_catalog_sections(
    manifest: dict[str, object], *, require_metadata: bool
) -> CatalogSections:
    must_command_contracts = _require_mapping(manifest, "must_command_contracts")
    command_tiers = _normalize_command_tiers(_require_mapping(manifest, "command_tiers"))
    command_metadata = (
        _require_mapping(manifest, "command_metadata")
        if require_metadata
        else _optional_mapping(manifest, "command_metadata")
    )
    return CatalogSections(
        must_command_contracts=must_command_contracts,
        command_tiers=command_tiers,
        command_metadata=command_metadata,
    )


def _validate_catalog_consistency(
    sections: CatalogSections,
    *,
    require_metadata: bool,
) -> list[str]:
    command_ids = sorted(sections.command_tiers)
    must_command_ids = {str(command) for command in sections.must_command_contracts}
    _raise_on_slug_collisions(command_ids, field_name="command_tiers")
    _raise_on_slug_collisions(sorted(must_command_ids), field_name="must_command_contracts")
    metadata_ids = set(
        _validate_command_ids(sections.command_metadata, field_name="command_metadata")
    )

    _raise_on_slug_collisions(
        sorted({*must_command_ids, *command_ids, *metadata_ids}),
        field_name="command_catalog",
    )

    missing_tiers = sorted(
        command for command in must_command_ids if command not in sections.command_tiers
    )
    if missing_tiers:
        details = ", ".join(missing_tiers)
        raise CommandSurfaceLoadError(
            f"must_command_contracts missing tier classification: {details}"
        )

    if require_metadata:
        missing_metadata = sorted(command for command in command_ids if command not in metadata_ids)
        if missing_metadata:
            details = ", ".join(missing_metadata)
            raise CommandSurfaceLoadError(f"command_metadata missing entries: {details}")

        extra_metadata = sorted(
            command for command in metadata_ids if command not in sections.command_tiers
        )
        if extra_metadata:
            details = ", ".join(extra_metadata)
            raise CommandSurfaceLoadError(f"command_metadata contains unknown commands: {details}")

    return command_ids


def _resolve_metadata_entry(
    command_metadata: RawMapping,
    command_id: str,
    *,
    require_metadata: bool,
) -> tuple[str, str, list[str]]:
    if not require_metadata:
        return "", "", []

    metadata_entry = command_metadata.get(command_id, {})
    if not isinstance(metadata_entry, Mapping):
        raise CommandSurfaceLoadError(f"command_metadata[{command_id}] must be a mapping")

    summary = _require_string(metadata_entry.get("summary"), field_name=f"{command_id}.summary")
    when_to_use = _require_string(
        metadata_entry.get("when_to_use"), field_name=f"{command_id}.when_to_use"
    )
    next_steps = _require_string_list(
        metadata_entry.get("next_steps"), field_name=f"{command_id}.next_steps"
    )
    return summary, when_to_use, next_steps


def _validate_next_steps(next_steps: list[str], *, command_id: str, command_ids: set[str]) -> None:
    invalid_next_steps = sorted(step for step in next_steps if step not in command_ids)
    if invalid_next_steps:
        details = ", ".join(invalid_next_steps)
        raise CommandSurfaceLoadError(
            f"{command_id}.next_steps contains unknown commands: {details}"
        )


def _resolve_required_contract_ids(
    must_command_contracts: RawMapping, command_id: str
) -> list[str]:
    command_payload = must_command_contracts.get(command_id)
    if command_payload is None:
        return []
    if not isinstance(command_payload, Mapping):
        raise CommandSurfaceLoadError(f"must_command_contracts[{command_id}] must be a mapping")
    return _require_string_list(
        command_payload.get("requires", []), field_name=f"{command_id}.requires"
    )


def _resolve_required_contracts(
    manifest: dict[str, object],
    command_id: str,
    required_contract_ids: list[str],
    *,
    require_contracts: bool,
) -> list[RequiredContractInfo]:
    if not require_contracts:
        return []

    required_contracts: list[RequiredContractInfo] = []
    for contract_id in required_contract_ids:
        contract = find_contract(manifest, contract_id)
        if contract is None:
            raise CommandSurfaceLoadError(f"{command_id} requires unknown contract: {contract_id}")
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
    return required_contracts


def _build_command_entry(context: CatalogBuildContext, command_id: str) -> CommandCatalogEntry:
    summary, when_to_use, next_steps = _resolve_metadata_entry(
        context.sections.command_metadata,
        command_id,
        require_metadata=context.require_metadata,
    )
    _validate_next_steps(next_steps, command_id=command_id, command_ids=context.command_ids)

    required_contract_ids = _resolve_required_contract_ids(
        context.sections.must_command_contracts,
        command_id,
    )
    required_contracts = _resolve_required_contracts(
        context.manifest,
        command_id,
        required_contract_ids,
        require_contracts=context.require_contracts,
    )

    return {
        "id": command_id,
        "slug": command_id.removeprefix("/"),
        "tier": context.sections.command_tiers[command_id],
        "summary": summary,
        "when_to_use": when_to_use,
        "next_steps": next_steps,
        "required_contracts": required_contracts,
    }


def _build_catalog(
    manifest: dict[str, object],
    sections: CatalogSections,
    command_ids: list[str],
    *,
    require_metadata: bool,
    require_contracts: bool,
) -> tuple[list[CommandCatalogEntry], dict[CommandTier, list[str]]]:
    commands: list[CommandCatalogEntry] = []
    tiers: dict[CommandTier, list[str]] = {"core": [], "conditional": []}
    context = CatalogBuildContext(
        manifest=manifest,
        sections=sections,
        require_metadata=require_metadata,
        require_contracts=require_contracts,
        command_ids=set(command_ids),
    )

    for command_id in command_ids:
        command_info = _build_command_entry(context, command_id)
        commands.append(command_info)
        tiers[command_info["tier"]].append(command_id)

    return commands, tiers


def load_command_catalog(
    repo_root: Path,
    manifest_path: str | Path,
    *,
    require_metadata: bool = True,
    require_contracts: bool = True,
) -> CommandCatalog:
    manifest, resolved_manifest_path = _load_manifest_payload(repo_root, manifest_path)
    _require_contract_section(manifest, require_contracts=require_contracts)
    _raise_on_invalid_command_ids(
        _require_mapping(manifest, "must_command_contracts"),
        field_name="must_command_contracts",
    )
    sections = _load_catalog_sections(manifest, require_metadata=require_metadata)
    command_ids = _validate_catalog_consistency(sections, require_metadata=require_metadata)
    commands, tiers = _build_catalog(
        manifest,
        sections,
        command_ids,
        require_metadata=require_metadata,
        require_contracts=require_contracts,
    )
    return {
        "manifest_path": _normalize_manifest_ref(repo_root, resolved_manifest_path),
        "commands": commands,
        "tiers": tiers,
    }
