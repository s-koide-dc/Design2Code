# -*- coding: utf-8 -*-
import os
import sys
import unittest
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from src.pipeline_core.pipeline_core import Pipeline


class TestResponseRewriterIntegration(unittest.TestCase):
    def _register_http_server_cleanup(self, server, thread):
        def _cleanup():
            server.shutdown()
            thread.join(timeout=1)
            server.server_close()

        self.addCleanup(_cleanup)

    def test_pipeline_run_uses_subprocess_rewriter_backend_when_enabled(self):
        pipeline = Pipeline(is_test_mode=True)
        pipeline.config_manager.response_rewriter_config = {
            "enabled": True,
            "provider": "subprocess_stdio",
            "command": [sys.executable, os.path.abspath("scripts/response_rewriter_stub_backend.py")],
            "response_format": "json",
            "timeout_seconds": 5,
            "prompt_contract": {
                "rewrite_style": "natural_japanese",
                "instruction": "与えられた response_text の事実を変えずに、日本語の自然さだけを整えてください。"
            },
            "max_input_chars": 1200,
            "max_length_ratio": 3.0,
            "rewrite_allowed_intents": ["SMALLTALK"],
            "rewrite_error_messages": False,
        }
        pipeline._response_generator = None

        result = pipeline.run("雑談しよう")

        self.assertIn("（自然化）", result.get("response", {}).get("text", ""))

    def test_pipeline_run_uses_openai_compatible_http_backend_when_enabled(self):
        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body_length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(body_length).decode("utf-8"))
                rewritten = payload["messages"][-1]["content"].split("response_text:\n", 1)[-1] + "（llama.cpp自然化）。"
                response = {
                    "choices": [
                        {
                            "message": {
                                "content": rewritten
                            }
                        }
                    ]
                }
                encoded = json.dumps(response, ensure_ascii=False).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def log_message(self, format, *args):
                return

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self._register_http_server_cleanup(server, thread)

        pipeline = Pipeline(is_test_mode=True)
        pipeline.config_manager.response_rewriter_config = {
            "enabled": True,
            "provider": "openai_compatible_http",
            "endpoint_url": f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
            "model": "local-llama",
            "timeout_seconds": 5,
            "max_new_tokens": 24,
            "prompt_contract": {
                "rewrite_style": "natural_japanese",
                "instruction": "与えられた response_text の事実を変えずに、日本語の自然さだけを整えてください。"
            },
            "max_input_chars": 1200,
            "max_length_ratio": 3.0,
            "rewrite_allowed_intents": ["SMALLTALK"],
            "rewrite_error_messages": False,
        }
        pipeline._response_generator = None

        result = pipeline.run("雑談しよう")

        self.assertIn("（llama.cpp自然化）", result.get("response", {}).get("text", ""))


if __name__ == "__main__":
    unittest.main()
