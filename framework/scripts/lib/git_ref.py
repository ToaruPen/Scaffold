from __future__ import annotations

import re

_SAFE_GIT_REF = re.compile(r"^[^\x00-\x20\x7f~^:?*\[\\;|&`'\"$()<>!]+$")


def validate_git_ref(value: str) -> str:
    if (
        not value
        or value.startswith("-")
        or value.startswith("/")
        or value.endswith("/")
        or value.endswith(".")
        or value.endswith(".lock")
        or "//" in value
        or ".." in value
        or "@{" in value
        or not _SAFE_GIT_REF.fullmatch(value)
    ):
        raise ValueError("invalid git ref")

    segments = value.split("/")
    if any(not segment or segment.startswith(".") for segment in segments):
        raise ValueError("invalid git ref")

    return value
