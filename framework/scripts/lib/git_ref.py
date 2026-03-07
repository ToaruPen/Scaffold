from __future__ import annotations

import re

_SAFE_GIT_REF = re.compile(r"^(?!.*\.\.)[A-Za-z0-9._/@+-]+$")


def validate_git_ref(value: str) -> str:
    if not value or value.startswith("-") or not _SAFE_GIT_REF.fullmatch(value):
        raise ValueError("invalid git ref")
    return value
