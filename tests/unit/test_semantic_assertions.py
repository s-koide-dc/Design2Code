# -*- coding: utf-8 -*-
import unittest

from src.code_verification.semantic_assertions import evaluate_blueprint_contract


class TestSemanticAssertions(unittest.TestCase):
    def test_validates_structured_intent_evidence_without_code_text(self):
        blueprint = {
            "methods": [
                {
                    "name": "LoadAndShow",
                    "body": [
                        {"type": "raw", "node_id": "step_1", "intent": "FILE_IO"},
                        {"type": "call", "node_id": "step_2", "intent": "DISPLAY"},
                    ],
                }
            ]
        }

        self.assertEqual(
            [],
            evaluate_blueprint_contract(
                blueprint,
                {
                    "require_intents": ["FILE_IO", "DISPLAY"],
                    "require_node_intents": [
                        {"node_id": "step_1", "intent": "FILE_IO"},
                        {"node_id": "step_2", "intent": "DISPLAY"},
                    ],
                },
            ),
        )

    def test_reports_missing_or_mismatched_structured_evidence(self):
        blueprint = {
            "methods": [
                {
                    "name": "Load",
                    "body": [{"type": "raw", "node_id": "step_1", "intent": "FILE_IO"}],
                }
            ]
        }

        issues = evaluate_blueprint_contract(
            blueprint,
            {
                "require_intents": ["DISPLAY"],
                "require_node_intents": [{"node_id": "step_1", "intent": "DISPLAY"}],
            },
        )

        self.assertIn("required intent is missing: DISPLAY", issues)
        self.assertIn("required intent DISPLAY is missing for node: step_1", issues)

    def test_validates_explicit_dataflow_evidence(self):
        blueprint = {
            "methods": [
                {
                    "name": "LoadAndShow",
                    "body": [
                        {"type": "raw", "node_id": "step_1", "intent": "FILE_IO"},
                        {
                            "type": "call",
                            "node_id": "step_2",
                            "intent": "DISPLAY",
                            "input_node_ids": ["step_1"],
                        },
                    ],
                }
            ]
        }

        self.assertEqual(
            [],
            evaluate_blueprint_contract(
                blueprint,
                {
                    "require_dataflow": [
                        {"source_node_id": "step_1", "consumer_node_id": "step_2"},
                    ],
                },
            ),
        )

    def test_reports_missing_dataflow_evidence(self):
        blueprint = {
            "methods": [
                {
                    "name": "LoadAndShow",
                    "body": [
                        {"type": "raw", "node_id": "step_1", "intent": "FILE_IO"},
                        {"type": "call", "node_id": "step_2", "intent": "DISPLAY"},
                    ],
                }
            ]
        }

        issues = evaluate_blueprint_contract(
            blueprint,
            {
                "require_dataflow": [
                    {"source_node_id": "step_1", "consumer_node_id": "step_2"},
                ],
            },
        )

        self.assertIn("required dataflow is missing: step_1 -> step_2", issues)

    def test_validates_display_property_evidence(self):
        blueprint = {
            "methods": [
                {
                    "name": "ShowName",
                    "body": [
                        {
                            "type": "raw",
                            "node_id": "step_2",
                            "intent": "DISPLAY",
                            "display_property": "Name",
                        },
                    ],
                }
            ]
        }

        self.assertEqual(
            [],
            evaluate_blueprint_contract(
                blueprint,
                {"require_display_properties": [{"node_id": "step_2", "property": "Name"}]},
            ),
        )

    def test_reports_missing_display_property_evidence(self):
        blueprint = {"methods": [{"name": "ShowName", "body": [{"type": "raw", "node_id": "step_2", "intent": "DISPLAY"}]}]}

        issues = evaluate_blueprint_contract(
            blueprint,
            {"require_display_properties": [{"node_id": "step_2", "property": "Name"}]},
        )

        self.assertIn("required display property is missing: step_2.Name", issues)

    def test_rejects_malformed_structured_contract(self):
        blueprint = {"methods": [{"name": "Load", "body": []}]}

        issues = evaluate_blueprint_contract(blueprint, {"require_intents": "DISPLAY"})

        self.assertIn("require_intents must be a list of non-empty intent names", issues)

    def test_detects_placeholder_and_missing_property_display(self):
        blueprint = {
            "methods": [
                {
                    "name": "BatchProcessProducts",
                    "body": [
                        {
                            "type": "call",
                            "method": "Enumerable.Empty<Item>",
                            "args": [],
                            "out_var": "items",
                        },
                        {
                            "type": "foreach",
                            "source": "items",
                            "item_name": "item",
                            "body": [
                                {
                                    "type": "call",
                                    "method": "Console.WriteLine",
                                    "args": ["item"],
                                }
                            ],
                        },
                    ],
                }
            ]
        }

        issues = evaluate_blueprint_contract(
            blueprint,
            {
                "disallow_placeholder_fetch": True,
                "require_display_property": "Name",
            },
        )

        self.assertTrue(any("placeholder fetch" in x for x in issues))
        self.assertTrue(any("displayed value" in x for x in issues))

    def test_detects_unconsumed_read_output(self):
        blueprint = {
            "methods": [
                {
                    "name": "RobustConfigLoader",
                    "body": [
                        {
                            "type": "call",
                            "method": "File.ReadAllText",
                            "args": ['"config.json"'],
                            "out_var": "configText",
                        },
                        {
                            "type": "call",
                            "method": "Console.WriteLine",
                            "args": ['"done"'],
                        },
                    ],
                }
            ]
        }

        issues = evaluate_blueprint_contract(
            blueprint,
            {
                "require_var_usage_from_methods": [{"method_suffix": "File.ReadAllText"}],
            },
        )

        self.assertTrue(any("not consumed" in x for x in issues))


if __name__ == "__main__":
    unittest.main()
