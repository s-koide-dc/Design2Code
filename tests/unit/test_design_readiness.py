from __future__ import annotations

import unittest
from pathlib import Path

from scripts.validate.review_design_readiness import ROOT, review_design


class TestDesignReadiness(unittest.TestCase):
    def test_blocks_missing_explicit_metadata_with_registered_guidance(self):
        result = review_design(ROOT / "tests" / "fixtures" / "designs" / "MissingStepMetadata.design.md")

        self.assertEqual("blocked", result["status"])
        issue = result["issues"][0]
        self.assertEqual("MISSING_EXPLICIT_STEP_METADATA", issue["reason"])
        self.assertEqual(
            "missing_step_metadata_missing_explicit_step_metadata",
            issue["known_failure_cases"][0]["case_id"],
        )

    def test_marks_explicit_supported_design_ready(self):
        result = review_design(ROOT / "scenarios" / "AppModeEchoMinimal.design.md")

        self.assertEqual("ready", result["status"])
        self.assertEqual([], result["issues"])

    def test_marks_compact_action_design_ready_after_deterministic_expansion(self):
        result = review_design(ROOT / "tests" / "fixtures" / "designs" / "CompactAppMode.design.md")

        self.assertEqual("ready", result["status"])
        self.assertEqual([], result["issues"])
