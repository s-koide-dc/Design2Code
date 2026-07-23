# -*- coding: utf-8 -*-
import unittest
from pathlib import Path

from src.design_parser.structured_parser import StructuredDesignParser
from src.design_parser.validator import StructuredSpecValidationError, validate_structured_spec


class TestStructuredDesignParser(unittest.TestCase):
    def setUp(self):
        self.parser = StructuredDesignParser()

    def test_parses_explicit_logic_tag_without_text_inference(self):
        sample_md = """
# ExplicitLogic
## 1. Purpose
明示 logic タグの解析。
## 2. Structured Specification
### Core Logic
1. [CONDITION|EXISTS|User|bool|NONE] [logic:[{\"type\":\"numeric\",\"variable_hint\":\"Points\",\"operator\":\"Greater\",\"expected_value\":100}]] 条件を確認する
"""

        spec = self.parser.parse_markdown(sample_md)

        self.assertEqual(
            [{"type": "numeric", "variable_hint": "Points", "operator": "Greater", "expected_value": 100}],
            spec["steps"][0]["logic"],
        )

    def test_complex_linq_scenario_declares_predicate_contracts(self):
        scenario_path = Path(__file__).resolve().parents[2] / "scenarios" / "ComplexLinqSearch.design.md"
        spec = self.parser.parse_design_file(str(scenario_path))

        self.assertEqual(
            [{"type": "string", "variable_hint": "Name", "operator": "StartsWith", "expected_value": "A"}],
            spec["steps"][2]["logic"],
        )
        self.assertEqual(
            [{"type": "numeric", "variable_hint": "Price", "operator": "Greater", "expected_value": 500}],
            spec["steps"][3]["logic"],
        )

    def test_conjunctive_linq_scenario_declares_ordered_predicate_contract(self):
        scenario_path = Path(__file__).resolve().parents[2] / "scenarios" / "ConjunctiveLinqSearch.design.md"
        spec = self.parser.parse_design_file(str(scenario_path))

        self.assertEqual(
            [
                {"type": "string", "variable_hint": "Name", "operator": "StartsWith", "expected_value": "A"},
                {"type": "conjunction", "value": "AND"},
                {"type": "numeric", "variable_hint": "Price", "operator": "Greater", "expected_value": 500},
            ],
            spec["steps"][2]["logic"],
        )

    def test_disjunctive_linq_scenario_declares_ordered_predicate_contract(self):
        scenario_path = Path(__file__).resolve().parents[2] / "scenarios" / "DisjunctiveLinqSearch.design.md"
        spec = self.parser.parse_design_file(str(scenario_path))

        self.assertEqual(
            [
                {"type": "string", "variable_hint": "Name", "operator": "StartsWith", "expected_value": "A"},
                {"type": "conjunction", "value": "OR"},
                {"type": "numeric", "variable_hint": "Price", "operator": "Greater", "expected_value": 500},
            ],
            spec["steps"][2]["logic"],
        )

    def test_rejects_malformed_explicit_logic_tag(self):
        sample_md = """
# InvalidLogic
## 1. Purpose
不正な logic タグを拒否する。
## 2. Structured Specification
### Core Logic
1. [CONDITION|EXISTS|User|bool|NONE] [logic:[{"type":"numeric"]] 条件を確認する
"""

        with self.assertRaisesRegex(StructuredSpecValidationError, "logic tag must contain valid JSON"):
            self.parser.parse_markdown(sample_md)

    def test_rejects_incomplete_explicit_predicate_goal(self):
        sample_md = """
# InvalidPredicate
## 1. Purpose
不完全な predicate goal を拒否する。
## 2. Structured Specification
### Core Logic
1. [CONDITION|EXISTS|User|bool|NONE] [logic:[{"type":"numeric","variable_hint":"Points","operator":"Greater"}]] 条件を確認する
"""

        with self.assertRaisesRegex(StructuredSpecValidationError, "numeric expected_value"):
            self.parser.parse_markdown(sample_md)

    def test_rejects_empty_or_unsupported_explicit_logic_goals(self):
        empty_logic = """
# EmptyLogic
## 1. Purpose
空の logic を拒否する。
## 2. Structured Specification
### Core Logic
1. [CONDITION|EXISTS|User|bool|NONE] [logic:[]] 条件を確認する
"""
        unsupported_goal = """
# UnsupportedLogic
## 1. Purpose
未対応 goal を拒否する。
## 2. Structured Specification
### Core Logic
1. [CONDITION|EXISTS|User|bool|NONE] [logic:[{"type":"calculation","variable_hint":"Points"}]] 条件を確認する
"""

        with self.assertRaisesRegex(StructuredSpecValidationError, "non-empty list"):
            self.parser.parse_markdown(empty_logic)
        with self.assertRaisesRegex(StructuredSpecValidationError, "type must be one of"):
            self.parser.parse_markdown(unsupported_goal)

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

    def test_parse_semantic_roles_with_array_value(self):
        sample_md = """
# OpsModule
## 1. Purpose
Validate semantic_roles array parsing.
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
1. [ACTION|TRANSFORM|string|string|NONE] [semantic_roles:{"ops":["trim_upper"]}] 入力を整形する
### Test Cases
- **Scenario**: Ops Parse
- **Expected**: ok
"""

        spec = self.parser.parse_markdown(sample_md)

        self.assertEqual(len(spec["steps"]), 1)
        self.assertEqual(spec["steps"][0]["semantic_roles"].get("ops"), ["trim_upper"])
        self.assertTrue(spec["steps"][0]["explicit_semantic_roles"])

    def test_parse_entity_specs_as_explicit_schema(self):
        sample_md = """
# CustomerModule
## 1. Purpose
Validate inline entity specs.
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Entity Specs
- Customer:
  - Id: int
  - Name: string
  - Points: int
### Core Logic
1. [ACTION|DISPLAY|Customer|void|NONE] 顧客を表示する
### Test Cases
- **Scenario**: Entity specs
- **Expected**: ok
"""

        spec = self.parser.parse_markdown(sample_md)

        self.assertEqual(
            spec["entity_specs"],
            [
                {
                    "name": "Customer",
                    "properties": {
                        "Id": "int",
                        "Name": "string",
                        "Points": "int",
                    },
                }
            ],
        )

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

    def test_validator_requires_path_or_file_source_for_file_fetch(self):
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
                    "output_type": "string",
                    "side_effect": "IO",
                    "text": "ファイルを読み込む",
                    "semantic_roles": {},
                    "source_kind": "file",
                    "depends_on": []
                }
            ]
        }
        errors = validate_structured_spec(spec)
        self.assertTrue(any("intent=FETCH source_kind=file requires source_ref(kind=file) or semantic_roles.path" in e for e in errors))

    def test_validator_accepts_literal_path_for_file_fetch(self):
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
                    "output_type": "string",
                    "side_effect": "IO",
                    "text": "users.json を読み込む",
                    "semantic_roles": {"path": "users.json"},
                    "source_kind": "file",
                    "depends_on": []
                }
            ]
        }
        errors = validate_structured_spec(spec)
        self.assertEqual(errors, [])

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

    def test_validator_requires_http_evidence_for_http_request(self):
        spec = {
            "module_name": "X",
            "purpose": "Y",
            "inputs": [],
            "outputs": [],
            "constraints": [],
            "test_cases": [],
            "data_sources": [{"id": "source_file", "kind": "file"}],
            "steps": [
                {
                    "id": "step_1",
                    "kind": "ACTION",
                    "intent": "HTTP_REQUEST",
                    "target_entity": "Item",
                    "input_refs": [],
                    "output_type": "string",
                    "side_effect": "NETWORK",
                    "text": "APIからJSON文字列を取得する",
                    "semantic_roles": {},
                    "source_ref": "source_file",
                    "depends_on": []
                }
            ]
        }
        errors = validate_structured_spec(spec)
        self.assertTrue(any("intent=HTTP_REQUEST requires source_ref(kind=http)" in e for e in errors))
        self.assertTrue(any("intent=HTTP_REQUEST requires source_kind=http" in e for e in errors))
        self.assertTrue(any("intent=HTTP_REQUEST requires semantic_roles.url" in e for e in errors))

    def test_validator_requires_sql_for_db_persist(self):
        spec = {
            "module_name": "X",
            "purpose": "Y",
            "inputs": [],
            "outputs": [],
            "constraints": [],
            "test_cases": [],
            "data_sources": [{"id": "local_db", "kind": "db"}],
            "steps": [
                {
                    "id": "step_1",
                    "kind": "ACTION",
                    "intent": "PERSIST",
                    "target_entity": "Item",
                    "input_refs": [],
                    "output_type": "void",
                    "side_effect": "DB",
                    "text": "商品を保存する",
                    "semantic_roles": {},
                    "source_ref": "local_db",
                    "source_kind": "db",
                    "depends_on": []
                }
            ]
        }
        errors = validate_structured_spec(spec)
        self.assertTrue(any("intent=PERSIST source_ref(kind=db) requires semantic_roles.sql" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
