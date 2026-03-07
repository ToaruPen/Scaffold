from __future__ import annotations

import unittest

from framework.scripts.lib import final_review_helpers
from framework.scripts.lib.paths_metadata import ReviewContext


def _context() -> ReviewContext:
    return ReviewContext(
        request_id="req-1",
        scope_id="issue-1",
        run_id="run-1",
        base_ref="main",
        head_sha="abc1234",
        base_sha="def5678",
        artifact_path=".scaffold/review_results/issue-1/run-1/final-review/outputs/final-review.json",
        engine="codex",
    )


class FinalReviewHelpersTests(unittest.TestCase):
    def test_build_drift_input_keeps_actual_changes_empty_when_no_changes(self) -> None:
        payload = final_review_helpers._build_drift_input(
            context=_context(),
            artifact_path="artifacts/drift.json",
            declared_targets=["framework/scripts/lib/"],
            changed_paths=[],
        )

        self.assertEqual(payload["actual_changes"], [])
        self.assertEqual(payload["declared_targets"], ["framework/scripts/lib/"])

    def test_build_drift_input_keeps_declared_fallback_behavior(self) -> None:
        payload = final_review_helpers._build_drift_input(
            context=_context(),
            artifact_path="artifacts/drift.json",
            declared_targets=[],
            changed_paths=["framework/scripts/lib/final_review_helpers.py"],
        )

        self.assertEqual(
            payload["actual_changes"], ["framework/scripts/lib/final_review_helpers.py"]
        )
        self.assertEqual(payload["declared_targets"], ["__missing_declared_targets__"])


if __name__ == "__main__":
    unittest.main()
