import unittest

from src.design_parser.inference_source_resolution import collect_source_kinds, select_source_override
from src.utils.semantic_intents import INTENT_FETCH, INTENT_HTTP_REQUEST


class TestInferenceSourceResolution(unittest.TestCase):
    def test_collects_sources_by_declared_kind(self):
        env, stdin, http, files = collect_source_kinds([
            {"id": "APP_MODE", "kind": "env"},
            {"id": "STDIN", "kind": "stdin"},
            {"id": "api", "kind": "http"},
            {"id": "input_path", "kind": "file"},
        ])
        self.assertEqual("APP_MODE", env[0]["id"])
        self.assertEqual("STDIN", stdin[0]["id"])
        self.assertEqual("api", http[0]["id"])
        self.assertEqual("input_path", files[0]["id"])

    def test_selects_single_http_source_only_with_explicit_url(self):
        result = select_source_override(
            "API 'https://example.test/items' を取得する",
            1,
            [], [], [{"id": "catalog", "kind": "http"}], [],
            lambda text: "https://example.test/items" if "https://" in text else "",
        )
        self.assertEqual(("catalog", "http", INTENT_HTTP_REQUEST), result)

    def test_selects_first_step_stdin_source(self):
        result = select_source_override(
            "標準入力を読み込む", 1, [], [{"id": "STDIN", "kind": "stdin"}], [], [], lambda _text: ""
        )
        self.assertEqual(("STDIN", "stdin", INTENT_FETCH), result)
