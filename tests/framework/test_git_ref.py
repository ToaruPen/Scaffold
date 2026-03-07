from __future__ import annotations

import shlex
import unittest

from framework.scripts.lib.git_ref import quote_git_ref_for_shell, validate_git_ref


class GitRefTests(unittest.TestCase):
    def test_accepts_normal_branch_ref(self) -> None:
        self.assertEqual(validate_git_ref("feature/review-hardening"), "feature/review-hardening")

    def test_accepts_git_refs_with_shell_metacharacters(self) -> None:
        valid_refs = [
            "feature!abc",
            "feature$abc",
            "feature(abc)",
            "feature;abc",
            "feature|abc",
            "feature&abc",
            "feature`abc`",
            "feature'abc",
            'feature"abc',
            "feature<abc>",
            "feature$(echo)",
            "feature>out",
        ]

        for ref in valid_refs:
            with self.subTest(ref=ref):
                self.assertEqual(validate_git_ref(ref), ref)

    def test_quotes_valid_shell_metachar_refs(self) -> None:
        quoted = quote_git_ref_for_shell("feature$(echo)")

        self.assertNotEqual(quoted, "feature$(echo)")
        self.assertEqual(shlex.split(quoted), ["feature$(echo)"])

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
        ]

        for ref in invalid_refs:
            with self.subTest(ref=ref), self.assertRaisesRegex(ValueError, "invalid git ref"):
                validate_git_ref(ref)


if __name__ == "__main__":
    unittest.main()
