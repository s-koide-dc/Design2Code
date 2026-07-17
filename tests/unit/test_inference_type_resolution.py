import unittest

from src.design_parser.inference_type_resolution import entity_from_structural_context


class TestInferenceTypeResolution(unittest.TestCase):
    def test_prefers_explicit_entity_over_output_type(self):
        result = entity_from_structural_context("List<Product>", {"target_entity": "Order"}, lambda _value: "Product")
        self.assertEqual("Order", result)

    def test_uses_output_type_when_role_is_absent(self):
        result = entity_from_structural_context("List<Product>", {}, lambda value: "Product" if value == "List<Product>" else "")
        self.assertEqual("Product", result)
