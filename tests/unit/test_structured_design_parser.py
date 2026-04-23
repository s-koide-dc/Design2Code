# -*- coding: utf-8 -*-
import unittest

from src.design_parser.structured_parser import StructuredDesignParser
from src.design_parser.validator import validate_structured_spec


class TestStructuredDesignParser(unittest.TestCase):
    def setUp(self):
        self.parser = StructuredDesignParser()

    def test_parse_markdown_to_structured_spec(self):
        sample_md = """
# SampleModule
## 1. Purpose
Create a sample module.
## 2. Structured Specification
### Input
- **Description**: user id
- **Type/Format**: string
### Output
- **Description**: status
- **Type/Format**: string
### Core Logic
1. Read input
2. Return status
### Test Cases
- **Scenario**: Happy Path
- **Input**: valid id
- **Expected**: ok
"""
        spec = self.parser.parse_markdown(sample_md)

        self.assertEqual(spec["module_name"], "SampleModule")
        self.assertGreaterEqual(len(spec["steps"]), 2)
        self.assertEqual(spec["steps"][0]["id"], "step_1")
        self.assertEqual(spec["test_cases"][0]["id"], "tc_1")
        self.assertIn("data_sources", spec)

        errors = validate_structured_spec(spec)
        self.assertEqual(errors, [])

    def test_parse_step_metadata_and_refs(self):
        sample_md = """
# StructuredMetaModule
## 1. Purpose
Validate explicit step metadata.
## 2. Structured Specification
### Input
- **Description**: records
- **Type/Format**: list
### Output
- **Description**: result
- **Type/Format**: list
### Core Logic
1. [data_source|source_user_db|db] User DB
2. [ACTION|FETCH|User|IEnumerable<User>|NONE|source_user_db] Fetch users
3. [CONDITION|EXISTS|User|bool|NONE] [refs:step_2] Check user exists
4. [LOOP|GENERAL|User|void|NONE] [refs:step_2] Iterate users
### Test Cases
- **Scenario**: Meta Parse
- **Input**: seed
- **Expected**: parsed
"""

        spec = self.parser.parse_markdown(sample_md)
        errors = validate_structured_spec(spec)
        self.assertEqual(errors, [])

        step2 = spec["steps"][0]
        self.assertEqual(step2["kind"], "ACTION")
        self.assertEqual(step2["intent"], "FETCH")
        self.assertEqual(step2["target_entity"], "User")
        self.assertEqual(step2["output_type"], "IEnumerable<User>")
        self.assertEqual(step2["side_effect"], "NONE")
        self.assertEqual(step2["source_ref"], "source_user_db")
        self.assertEqual(step2["source_kind"], "db")

        step3 = spec["steps"][1]
        self.assertEqual(step3["kind"], "CONDITION")
        self.assertEqual(step3["input_refs"], ["step_2"])
        self.assertEqual(step3["depends_on"], ["step_2"])

        step4 = spec["steps"][2]
        self.assertEqual(step4["kind"], "LOOP")
        self.assertEqual(step4["input_refs"], ["step_2"])

    def test_parse_data_source_declaration_line(self):
        sample_md = """
# DataSourceModule
## 1. Purpose
Validate data source directive.
## 2. Structured Specification
### Input
- **Description**: request
- **Type/Format**: string
### Output
- **Description**: result
- **Type/Format**: string
### Core Logic
1. [data_source|source_orders_file|file] orders.csv
2. [ACTION|FETCH|Order|IEnumerable<Order>|NONE|source_orders_file] 注文を取得する
### Test Cases
- **Scenario**: Data source parse
- **Input**: any
- **Expected**: ok
"""

        spec = self.parser.parse_markdown(sample_md)
        self.assertEqual(len(spec["data_sources"]), 1)
        self.assertEqual(spec["data_sources"][0]["id"], "source_orders_file")
        self.assertEqual(spec["data_sources"][0]["kind"], "file")
        self.assertEqual(spec["data_sources"][0]["description"], "orders.csv")
        self.assertEqual(len(spec["steps"]), 1)
        self.assertEqual(spec["steps"][0]["source_ref"], "source_orders_file")

        errors = validate_structured_spec(spec)
        self.assertEqual(errors, [])

    def test_validator_reports_missing_required(self):
        bad_spec = {"module_name": "X"}
        errors = validate_structured_spec(bad_spec)
        self.assertTrue(any("missing top-level key" in e for e in errors))

    def test_validator_requires_source_ref_for_fetch(self):
        spec = {
            "module_name": "X",
            "purpose": "Y",
            "inputs": [],
            "outputs": [],
            "constraints": [],
            "test_cases": [],
            "data_sources": [],
            "steps": [
                {
                    "id": "step_1",
                    "kind": "ACTION",
                    "intent": "FETCH",
                    "target_entity": "User",
                    "input_refs": [],
                    "output_type": "IEnumerable<User>",
                    "side_effect": "NONE",
                    "text": "ユーザーを取得する",
                    "semantic_roles": {},
                    "depends_on": []
                }
            ]
        }
        errors = validate_structured_spec(spec)
        self.assertTrue(any("intent=FETCH requires valid source_ref" in e for e in errors))

    def test_validator_requires_db_evidence_for_database_query(self):
        spec = {
            "module_name": "X",
            "purpose": "Y",
            "inputs": [],
            "outputs": [],
            "constraints": [],
            "test_cases": [],
            "data_sources": [{"id": "source_http", "kind": "http"}],
            "steps": [
                {
                    "id": "step_1",
                    "kind": "ACTION",
                    "intent": "DATABASE_QUERY",
                    "target_entity": "Item",
                    "input_refs": [],
                    "output_type": "IEnumerable<Item>",
                    "side_effect": "DB",
                    "text": "在庫を取得する",
                    "semantic_roles": {},
                    "source_ref": "source_http",
                    "depends_on": []
                }
            ]
        }
        errors = validate_structured_spec(spec)
        self.assertTrue(any("intent=DATABASE_QUERY requires source_ref(kind=db)" in e for e in errors))
        self.assertTrue(any("intent=DATABASE_QUERY requires semantic_roles.sql" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
