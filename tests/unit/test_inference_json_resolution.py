import unittest

from src.design_parser.inference_json_resolution import infer_json_deserialize_meta


class TestInferenceJsonResolution(unittest.TestCase):
    def test_prefers_structural_entity_without_text_inference(self):
        result = infer_json_deserialize_meta(
            "データをリストに変換する", "string", {"target_entity": "User"}, False,
            lambda _line: True, lambda _output, roles: roles.get("target_entity"), lambda _line: None,
        )
        self.assertEqual("User", result["target_entity"])
        self.assertEqual("List<User>", result["output_type"])

    def test_returns_none_when_entity_is_not_explicitly_resolvable(self):
        result = infer_json_deserialize_meta(
            "データをリストに変換する", "string", {}, False,
            lambda _line: True, lambda _output, _roles: None, lambda _line: "User",
        )
        self.assertIsNone(result)
