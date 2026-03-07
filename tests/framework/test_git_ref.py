from __future__ import annotations

import unittest

from framework.scripts.lib.git_ref import validate_git_ref


class GitRefTests(unittest.TestCase):
    def test_accepts_normal_branch_ref(self) -> None:
        self.assertEqual(validate_git_ref("feature/review-hardening"), "feature/review-hardening")

    def test_rejects_forbidden_git_ref_patterns(self) -> None:
        invalid_refs = [
            "",
            "-main",
            "/main",
            "main/",
            "main.",
            "main.lock",
            "main//sub",
            "main..sub",
            "main@{1}",
            "refs/.hidden/main",
            "refs/heads/.topic",
            "main branch",
            "main~1",
            "main^",
            "main:topic",
            "main?topic",
            "main*topic",
            "main[topic",
            r"main\topic",
            "origin/main;echo",
            "origin/main|cat",
            "origin/main&echo",
            "origin/main`echo`",
            "origin/main'quote",
            'origin/main"quote',
            "origin/main$(echo)",
            "origin/main>out",
        ]

        for ref in invalid_refs:
            with self.subTest(ref=ref), self.assertRaisesRegex(ValueError, "invalid git ref"):
                validate_git_ref(ref)


if __name__ == "__main__":
    unittest.main()
