#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def error_dict(code: str, message: str, provider: str) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "retryable": False,
        "provider": provider,
    }


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"failed to read input JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("input must be a JSON object")
    return data


def require_text(obj: dict[str, Any], key: str, parent: str = "") -> str:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"missing or invalid string: {prefix}{key}")
    return raw.strip()


def optional_text(obj: dict[str, Any], key: str, parent: str = "") -> str | None:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if raw is None:
        return None
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"invalid string: {prefix}{key}")
    return raw.strip()


def require_object(obj: dict[str, Any], key: str, parent: str = "") -> dict[str, Any]:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if not isinstance(raw, dict):
        raise ValueError(f"missing or invalid object: {prefix}{key}")
    return raw


def require_bool(obj: dict[str, Any], key: str, parent: str = "") -> bool:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if not isinstance(raw, bool):
        raise ValueError(f"missing or invalid boolean: {prefix}{key}")
    return raw


def require_int(obj: dict[str, Any], key: str, parent: str = "") -> int:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise ValueError(f"missing or invalid integer: {prefix}{key}")
    return raw


def require_list_of_texts(obj: dict[str, Any], key: str, parent: str = "") -> list[str]:
    raw = obj.get(key)
    prefix = f"{parent}." if parent else ""
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"missing or invalid non-empty list: {prefix}{key}")

    values: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"invalid string element: {prefix}{key}")
        values.append(item.strip())
    return values


def write_result(result: dict[str, Any], output_path: Path | None) -> None:
    output_text = json.dumps(result, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
    print(output_text, end="")


def parse_gate_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--input", required=True, help="Path to input JSON")
    parser.add_argument("--output", help="Path to write result JSON")
    return parser.parse_args()
