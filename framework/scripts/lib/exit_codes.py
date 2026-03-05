from __future__ import annotations

EXIT_SUCCESS = 0
EXIT_VALIDATION_FAILED = 2

EXIT_SOFTWARE_ERROR = 70
EXIT_TIMEOUT = 124
EXIT_CANNOT_EXECUTE = 126
EXIT_COMMAND_NOT_FOUND = 127


def is_success(returncode: int) -> bool:
    return returncode == EXIT_SUCCESS
