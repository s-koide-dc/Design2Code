import unittest

from src.design_parser.inference_context import InferenceContext


class TestInferenceContext(unittest.TestCase):
    def test_context_captures_line_inference_snapshot(self):
        context = InferenceContext(2, "Sample", "List<User>", "bool", False, None, {"property": "Name"}, ({"id": "users", "kind": "file"},))
        self.assertEqual("List<User>", context.last_output_type)
        self.assertEqual("users", context.data_sources[0]["id"])
