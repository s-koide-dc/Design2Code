# -*- coding: utf-8 -*-
import unittest

from src.code_verification.semantic_assertions import evaluate_blueprint_contract


class TestSemanticAssertions(unittest.TestCase):
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
