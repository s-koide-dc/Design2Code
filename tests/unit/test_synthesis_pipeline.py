import unittest
from unittest.mock import MagicMock, patch

from src.code_synthesis.synthesis_pipeline import synthesize_structured_spec


class TestSynthesisPipeline(unittest.TestCase):
    @patch("src.code_synthesis.synthesis_pipeline.validate_structured_spec_or_raise")
    def test_spec_audit_failure_is_reported_as_blocking_issue(self, _validate):
        synthesizer = MagicMock()
        synthesizer.synthesize_from_structured_spec.return_value = {
            "status": "SUCCESS",
            "code": "public class Generated {}",
            "trace": {},
            "dependencies": [],
        }
        auditor = MagicMock()
        auditor.audit.side_effect = RuntimeError("audit unavailable")

        result = synthesize_structured_spec(
            synthesizer,
            {"steps": []},
            "Generated",
            spec_auditor=auditor,
        )

        self.assertEqual(
            result["spec_issues"],
            ["SPEC_AUDIT_ERROR|RuntimeError"],
        )
