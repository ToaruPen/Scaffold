from __future__ import annotations

import unittest

from framework.scripts.lib import exit_codes


class ExitCodesTests(unittest.TestCase):
    def test_exit_code_values_are_stable(self) -> None:
        self.assertEqual(exit_codes.EXIT_SUCCESS, 0)
        self.assertEqual(exit_codes.EXIT_VALIDATION_FAILED, 2)
        self.assertEqual(exit_codes.EXIT_SOFTWARE_ERROR, 70)
        self.assertEqual(exit_codes.EXIT_TIMEOUT, 124)
        self.assertEqual(exit_codes.EXIT_CANNOT_EXECUTE, 126)
        self.assertEqual(exit_codes.EXIT_COMMAND_NOT_FOUND, 127)

    def test_is_success(self) -> None:
        self.assertTrue(exit_codes.is_success(exit_codes.EXIT_SUCCESS))
        self.assertFalse(exit_codes.is_success(exit_codes.EXIT_VALIDATION_FAILED))


if __name__ == "__main__":
    unittest.main()
