from __future__ import annotations

from typing import Any


def _collect_unique_contracts(commands: list[dict[str, Any]]) -> list[str]:
    unique_contracts: list[str] = []
    for command in commands:
        for contract_id in command.get("requires", []):
            if contract_id not in unique_contracts:
                unique_contracts.append(contract_id)
    return unique_contracts


def _extend_contract_lines(lines: list[str], contract_ids: list[str]) -> None:
    lines.append("contracts:")
    if not contract_ids:
        lines.append("  []")
        return
    for contract_id in contract_ids:
        lines.extend(
            [
                f"  - id: {contract_id}",
                f"    description: {contract_id} description",
                f"    validator: framework/scripts/gates/{contract_id}.py",
            ]
        )


def _extend_must_contract_lines(lines: list[str], commands: list[dict[str, Any]]) -> None:
    lines.append("must_command_contracts:")
    for command in commands:
        lines.append(f"  {command['id']}:")
        lines.append("    requires:")
        for contract_id in command.get("requires", []):
            lines.append(f"      - {contract_id}")


def _extend_tier_lines(lines: list[str], commands: list[dict[str, Any]]) -> None:
    lines.append("command_tiers:")
    for command in commands:
        lines.append(f"  {command['id']}: {command['tier']}")


def _extend_metadata_lines(lines: list[str], commands: list[dict[str, Any]]) -> None:
    lines.append("command_metadata:")
    for command in commands:
        lines.append(f"  {command['id']}:")
        lines.append(f"    summary: Summary for {command['id']}")
        lines.append(f"    when_to_use: When to use {command['id']}")
        lines.append("    next_steps:")
        for next_step in command.get("next_steps", []):
            lines.append(f"      - {next_step}")


def build_manifest(
    commands: list[dict[str, Any]],
    *,
    include_metadata: bool = True,
    contract_lines: list[str] | None = None,
) -> str:
    lines: list[str] = []
    if contract_lines is not None:
        lines.extend(contract_lines)
    else:
        _extend_contract_lines(lines, _collect_unique_contracts(commands))

    _extend_must_contract_lines(lines, commands)
    _extend_tier_lines(lines, commands)
    if include_metadata:
        _extend_metadata_lines(lines, commands)
    return "\n".join(lines) + "\n"
