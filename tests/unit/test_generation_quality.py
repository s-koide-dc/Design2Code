# -*- coding: utf-8 -*-
import unittest

from src.config.config_manager import ConfigManager
from src.design_parser.structured_parser import StructuredDesignParser
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.utils.logic_auditor import LogicAuditor
from src.utils.spec_auditor import SpecAuditor
from src.utils.design_doc_parser import DesignDocParser
from src.utils.design_doc_refiner import DesignDocRefiner
from src.test_generator.test_generator import TestGenerator


class DummyKnowledgeBase:
    def __init__(self, data):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


class TestGenerationQuality(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()
        self.parser = StructuredDesignParser()
        self.synthesizer = CodeSynthesizer(self.config)

    def test_calculate_order_discount_uses_customer_type(self):
        spec = self.parser.parse_design_file("scenarios/CalculateOrderDiscount.design.md")
        result = self.synthesizer.synthesize_from_structured_spec(
            spec.get("module_name"),
            spec,
            return_trace=True
        )
        code = result.get("code", "")
        self.assertIn("CustomerType == \"Premium\"", code)
        self.assertNotIn("Id == \"Premium\"", code)

    def test_logic_auditor_uses_ukb_operator_direct_map(self):
        kb = DummyKnowledgeBase({
            "logic_audit": {
                "operator_direct_map": {
                    "超ぴ": "Greater"
                }
            }
        })
        auditor = LogicAuditor(knowledge_base=kb)
        goals = auditor.extract_assertion_goals(["合計が 100超ぴ の場合"])
        operators = [g.get("operator") for g in goals if g.get("type") in ["numeric", "string"]]
        self.assertIn("Greater", operators)

    def test_spec_auditor_uses_ukb_async_markers(self):
        kb = DummyKnowledgeBase({
            "spec_audit": {
                "async_markers": ["asyncx"]
            }
        })
        auditor = SpecAuditor(knowledge_base=kb)
        spec = {"outputs": [{"description": "asyncx output", "type_format": "bool"}]}
        self.assertTrue(auditor._spec_allows_async(spec, []))

    def test_design_doc_parser_uses_ukb_section_aliases(self):
        kb = DummyKnowledgeBase({
            "design_doc_parser": {
                "section_aliases": {
                    "purpose": ["PurposeX"]
                }
            }
        })
        parser = DesignDocParser(knowledge_base=kb)
        content = "# Sample\n## PurposeX\nCustom purpose"
        result = parser.parse_content(content)
        self.assertEqual("Custom purpose", result.get("purpose"))

    def test_design_doc_refiner_uses_ukb_placeholder_pattern(self):
        class DummyConfig:
            def __init__(self, kb):
                self.knowledge_base = kb

        kb = DummyKnowledgeBase({
            "design_doc_refiner": {
                "logic_placeholder_pattern": r"PLACEHOLDER"
            }
        })
        refiner = DesignDocRefiner(config_manager=DummyConfig(kb), knowledge_base=kb)
        content = "PLACEHOLDER"
        result = refiner._refine_logic_placeholders(content, {"classes": [], "functions": []})
        self.assertNotIn("PLACEHOLDER", result)

    def test_test_generator_uses_ukb_default_original_condition(self):
        kb = DummyKnowledgeBase({
            "test_generator": {
                "default_original_condition": "Custom default"
            }
        })
        gen = TestGenerator(knowledge_base=kb)
        class_info = {"name": "Sample"}
        m_info = {"name": "DoWork", "return_type": "bool", "parameters": ""}
        scenario = {"type": "happy_path", "condition": "Default", "expected_behavior": "Success"}
        code = gen._generate_method_test_code(class_info, m_info, scenario, "csharp")
        self.assertIn("Custom default", code)


if __name__ == "__main__":
    unittest.main()
