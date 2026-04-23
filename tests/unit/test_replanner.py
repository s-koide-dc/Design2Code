# -*- coding: utf-8 -*-
import unittest
from src.replanner.replanner import Replanner
from src.replanner.reason_analyzer import ReasonAnalyzer
from src.replanner.ir_patcher import IRPatcher

class TestReplanner(unittest.TestCase):
    def setUp(self):
        self.config = {}
        self.replanner = Replanner(self.config)

    def test_reason_analyzer_compilation_error(self):
        analyzer = ReasonAnalyzer()
        verification_result = {
            "valid": False,
            "errors": [
                {"code": "CS0103", "message": "The name 'x' does not exist in the current context", "symbol": "x"}
            ]
        }
        hints = analyzer.analyze({}, verification_result, [])
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["reason"], "MISSING_DECLARATION")
        self.assertEqual(hints[0]["patch"]["type"], "ENSURE_FIELD_OR_LOCAL")

    def test_reason_analyzer_semantic_issue(self):
        analyzer = ReasonAnalyzer()
        semantic_issues = ["required call is missing: SaveChangesAsync [step_1]"]
        hints = analyzer.analyze({}, {"valid": True}, semantic_issues)
        self.assertEqual(len(hints), 1)
        self.assertEqual(hints[0]["reason"], "SEMANTIC_CALL_MISSING")
        self.assertEqual(hints[0]["patch"]["type"], "FORCE_INTENT_RESOLUTION")
        self.assertEqual(hints[0]["patch"]["target_id"], "step_1")

    def test_ir_patcher_intent(self):
        patcher = IRPatcher()
        ir_tree = {
            "logic_tree": [
                {"id": "step_1", "type": "ACTION", "intent": "FETCH", "text": "Get data"}
            ]
        }
        hints = [
            {
                "reason": "SEMANTIC_CALL_MISSING",
                "patch": {"type": "FORCE_INTENT_RESOLUTION", "method": "SaveChangesAsync", "target_id": "step_1"}
            }
        ]
        patched_ir = patcher.apply_patches(ir_tree, hints)
        self.assertEqual(patched_ir["logic_tree"][0]["intent"], "PERSIST")

    def test_ir_patcher_links(self):
        patcher = IRPatcher()
        ir_tree = {
            "logic_tree": [
                {"id": "step_1", "type": "ACTION", "intent": "FETCH", "output_type": "IEnumerable<User>"},
                {"id": "step_2", "type": "ACTION", "intent": "DISPLAY", "input_refs": []}
            ]
        }
        hints = [
            {
                "reason": "DATA_FLOW_DISCONNECTION",
                "patch": {"type": "REBIND_INPUT_LINK", "source_id": "step_1", "target_id": "step_2"}
            }
        ]
        patched_ir = patcher.apply_patches(ir_tree, hints)
        self.assertIn("step_1", patched_ir["logic_tree"][1]["input_refs"])

if __name__ == "__main__":
    unittest.main()
