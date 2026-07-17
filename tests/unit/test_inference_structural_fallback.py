import unittest

from src.design_parser.inference_structural_fallback import resolve_source_fallback


class _Engine:
    def _infer_plain_stdin_fetch_meta(self, *_args): return None
    def _infer_plain_env_fetch_meta(self, *_args): return {"intent": "FETCH"}
    def _infer_plain_http_request_meta(self, *_args): return {"intent": "HTTP_REQUEST"}, {"url": "https://unused"}
    def _infer_plain_file_source_fetch_meta(self, *_args): return None, {}
    def _infer_plain_file_fetch_meta(self, *_args): return None, {}


class TestInferenceStructuralFallback(unittest.TestCase):
    def test_environment_precedes_http_when_both_resolve(self):
        meta, roles = resolve_source_fallback(_Engine(), "line", 1, [{"id": "APP_MODE"}], [], [{"id": "api"}], [])
        self.assertEqual({"intent": "FETCH"}, meta)
        self.assertEqual({}, roles)

    def test_http_is_selected_when_earlier_sources_do_not_resolve(self):
        engine = _Engine()
        engine._infer_plain_env_fetch_meta = lambda *_args: None
        meta, roles = resolve_source_fallback(engine, "line", 1, [], [], [{"id": "api"}], [])
        self.assertEqual({"intent": "HTTP_REQUEST"}, meta)
        self.assertEqual({"url": "https://unused"}, roles)

    def test_file_source_is_selected_after_http_has_no_candidate(self):
        engine = _Engine()
        engine._infer_plain_env_fetch_meta = lambda *_args: None
        engine._infer_plain_http_request_meta = lambda *_args: (None, {})
        engine._infer_plain_file_source_fetch_meta = lambda *_args: ({"intent": "FETCH"}, {"path": "input_path"})
        meta, roles = resolve_source_fallback(engine, "line", 1, [], [], [], [{"id": "input_path"}])
        self.assertEqual({"intent": "FETCH"}, meta)
        self.assertEqual({"path": "input_path"}, roles)
