from __future__ import annotations

import unittest

from framework.scripts.ci import readonly_review_shell


class ReadonlyReviewShellTests(unittest.TestCase):
    def test_builds_diff_command_for_valid_base_ref(self) -> None:
        command = readonly_review_shell._command_for_action(["git-diff", "origin/main"])

        self.assertEqual(
            command,
            ["git", "diff", "--stat", "--patch", "--unified=5", "origin/main...HEAD"],
        )

    def test_rejects_invalid_git_ref(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid git ref"):
            readonly_review_shell._command_for_action(["git-diff", "--cached"])

    def test_rejects_unknown_action(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported action"):
            readonly_review_shell._command_for_action(["git-push"])


if __name__ == "__main__":
    unittest.main()
