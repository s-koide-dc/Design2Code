# -*- coding: utf-8 -*-
import json
import sys
import tempfile
import textwrap
import unittest
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from src.response_rewriter.response_rewriter import ResponseRewriter
from src.utils.dialogue_state import PENDING_CONFIRMATION, TASK_CLARIFICATION


class _Config:
    def __init__(self, config):
        self.response_rewriter_config = config


class TestResponseRewriter(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.script_path = Path(self.temp_dir.name) / "rewrite_backend.py"

    def _write_backend(self, body: str):
        self.script_path.write_text(
            textwrap.dedent(body),
            encoding="utf-8",
        )

    def _build_config(self, **overrides):
        config = {
            "enabled": True,
            "provider": "subprocess_stdio",
            "command": [sys.executable, str(self.script_path)],
            "response_format": "json",
            "timeout_seconds": 5,
            "prompt_contract": {},
            "rewrite_allowed_intents": ["GENERAL"],
            "max_input_chars": 1200,
            "max_length_ratio": 10.0,
            "rewrite_confirmation_messages": False,
            "rewrite_clarification_messages": False,
            "rewrite_error_messages": False,
        }
        config.update(overrides)
        return _Config(config)

    def _register_http_server_cleanup(self, server, thread):
        def _cleanup():
            server.shutdown()
            thread.join(timeout=1)
            server.server_close()

        self.addCleanup(_cleanup)

    def test_subprocess_backend_rewrites_text_via_json_contract(self):
        self._write_backend(
            """
            import json
            import sys

            payload = json.loads(sys.stdin.read())
            text = payload["input"]["response_text"] + " [rewritten]."
            sys.stdout.write(json.dumps({"text": text}, ensure_ascii=False))
            """
        )
        rewriter = ResponseRewriter(
            config_manager=self._build_config(
                prompt_contract={
                    "rewrite_style": "natural_japanese",
                    "instruction": "与えられた response_text の事実を変えずに、日本語の自然さだけを整えてください。"
                },
                max_length_ratio=3.0,
            )
        )

        result = rewriter.rewrite(
            {"analysis": {"intent": "GENERAL"}, "response": {}},
            "元の応答です。",
        )

        self.assertEqual(result, "元の応答です。 [rewritten].")

    def test_subprocess_backend_falls_back_on_nonzero_exit(self):
        self._write_backend(
            """
            import sys
            sys.exit(3)
            """
        )
        rewriter = ResponseRewriter(config_manager=self._build_config(max_length_ratio=1.6))

        result = rewriter.rewrite(
            {"analysis": {"intent": "GENERAL"}, "response": {}},
            "元の応答です。",
        )

        self.assertEqual(result, "元の応答です。")

    def test_subprocess_backend_falls_back_when_output_contains_structured_markup(self):
        self._write_backend(
            """
            import json
            import sys

            sys.stdout.write(json.dumps({"text": "```python\\nprint('x')\\n```"}, ensure_ascii=False))
            """
        )
        rewriter = ResponseRewriter(config_manager=self._build_config(max_length_ratio=1.6))

        result = rewriter.rewrite(
            {"analysis": {"intent": "GENERAL"}, "response": {}},
            "元の応答です。",
        )

        self.assertEqual(result, "元の応答です。")

    def test_subprocess_backend_sends_versioned_payload_contract(self):
        self._write_backend(
            """
            import json
            import sys

            payload = json.loads(sys.stdin.read())
            result = {
                "text": "|".join([
                    payload["contract_version"],
                    payload["mode"],
                    payload["constraints"]["rewrite_style"],
                    str(payload["constraints"]["forbid_code_generation"]),
                    payload["input"]["intent"] or "",
                ]) + "。"
            }
            sys.stdout.write(json.dumps(result, ensure_ascii=False))
            """
        )
        rewriter = ResponseRewriter(
            config_manager=self._build_config(
                prompt_contract={
                    "rewrite_style": "natural_japanese",
                    "instruction": "契約テスト"
                },
                rewrite_allowed_intents=["GREETING"],
            )
        )

        result = rewriter.rewrite(
            {"analysis": {"intent": "GREETING"}, "response": {}},
            "元の応答です。",
        )

        self.assertEqual(result, "1.0|rewrite_response_text|natural_japanese|True|GREETING。")

    def test_confirmation_message_is_not_rewritten_by_default(self):
        self._write_backend(
            """
            import json
            import sys
            sys.stdout.write(json.dumps({"text": "書き換え済み"}, ensure_ascii=False))
            """
        )
        rewriter = ResponseRewriter(config_manager=self._build_config())

        result = rewriter.rewrite(
            {"dialogue_state": PENDING_CONFIRMATION, "analysis": {"intent": "CMD_RUN"}},
            "コマンドを実行します。よろしいですか？",
        )

        self.assertEqual(result, "コマンドを実行します。よろしいですか？")

    def test_clarification_message_is_not_rewritten_by_default(self):
        self._write_backend(
            """
            import json
            import sys
            sys.stdout.write(json.dumps({"text": "書き換え済み"}, ensure_ascii=False))
            """
        )
        rewriter = ResponseRewriter(config_manager=self._build_config())

        result = rewriter.rewrite(
            {
                "dialogue_state": TASK_CLARIFICATION,
                "clarification_needed": True,
                "analysis": {"intent": "FILE_CREATE"},
            },
            "ファイル名を教えていただけますか？",
        )

        self.assertEqual(result, "ファイル名を教えていただけますか？")

    def test_clarification_message_can_be_rewritten_when_explicitly_enabled(self):
        self._write_backend(
            """
            import json
            import sys
            sys.stdout.write(json.dumps({"text": "やわらかく言い換えました。"}, ensure_ascii=False))
            """
        )
        rewriter = ResponseRewriter(
            config_manager=self._build_config(rewrite_clarification_messages=True)
        )

        result = rewriter.rewrite(
            {
                "dialogue_state": TASK_CLARIFICATION,
                "clarification_needed": True,
                "analysis": {"intent": "FILE_CREATE"},
            },
            "ファイル名を教えていただけますか？",
        )

        self.assertEqual(result, "やわらかく言い換えました。")

    def test_action_intent_is_not_rewritten_by_default_even_on_success(self):
        self._write_backend(
            """
            import json
            import sys
            sys.stdout.write(json.dumps({"text": "作業完了を言い換えました"}, ensure_ascii=False))
            """
        )
        rewriter = ResponseRewriter(config_manager=self._build_config())

        result = rewriter.rewrite(
            {
                "analysis": {"intent": "FILE_CREATE"},
                "action_result": {"status": "success"},
            },
            "ファイル 'sample.txt' を作成しました。",
        )

        self.assertEqual(result, "ファイル 'sample.txt' を作成しました。")

    def test_general_message_is_not_rewritten_when_no_allow_list_is_provided(self):
        self._write_backend(
            """
            import json
            import sys
            sys.stdout.write(json.dumps({"text": "書き換え済みです。"}, ensure_ascii=False))
            """
        )
        config = _Config(
            {
                "enabled": True,
                "provider": "subprocess_stdio",
                "command": [sys.executable, str(self.script_path)],
                "response_format": "json",
                "timeout_seconds": 5,
                "prompt_contract": {},
                "max_input_chars": 1200,
                "max_length_ratio": 3.0,
                "rewrite_confirmation_messages": False,
                "rewrite_clarification_messages": False,
                "rewrite_error_messages": False,
            }
        )
        rewriter = ResponseRewriter(config_manager=config)

        result = rewriter.rewrite(
            {
                "analysis": {"intent": "GENERAL"},
                "action_result": {"status": "success"},
            },
            "進捗をご報告します。",
        )

        self.assertEqual(result, "進捗をご報告します。")

    def test_smalltalk_message_is_not_rewritten_when_allow_list_is_explicitly_empty(self):
        self._write_backend(
            """
            import json
            import sys
            sys.stdout.write(json.dumps({"text": "書き換え済みです。"}, ensure_ascii=False))
            """
        )
        rewriter = ResponseRewriter(
            config_manager=self._build_config(rewrite_allowed_intents=[])
        )

        result = rewriter.rewrite(
            {
                "analysis": {"intent": "SMALLTALK"},
                "action_result": {"status": "success"},
            },
            "もちろんです。少しお話ししましょうか。",
        )

        self.assertEqual(result, "もちろんです。少しお話ししましょうか。")

    def test_action_intent_can_be_rewritten_when_explicitly_allowed(self):
        self._write_backend(
            """
            import json
            import sys
            sys.stdout.write(json.dumps({"text": "ファイル 'sample.txt' を用意しました。"}, ensure_ascii=False))
            """
        )
        rewriter = ResponseRewriter(
            config_manager=self._build_config(rewrite_allowed_intents=["FILE_CREATE"])
        )

        result = rewriter.rewrite(
            {
                "analysis": {"intent": "FILE_CREATE"},
                "action_result": {"status": "success"},
            },
            "ファイル 'sample.txt' を作成しました。",
        )

        self.assertEqual(result, "ファイル 'sample.txt' を用意しました。")

    def test_non_success_action_status_is_not_rewritten_when_status_allow_list_is_present(self):
        self._write_backend(
            """
            import json
            import sys
            sys.stdout.write(json.dumps({"text": "途中経過を言い換えました"}, ensure_ascii=False))
            """
        )
        rewriter = ResponseRewriter(
            config_manager=self._build_config(rewrite_allowed_action_statuses=["success"])
        )

        result = rewriter.rewrite(
            {
                "analysis": {"intent": "GENERAL"},
                "action_result": {"status": "in_progress"},
            },
            "処理を進めています。",
        )

        self.assertEqual(result, "処理を進めています。")

    def test_resolve_command_expands_python_and_workspace_placeholders(self):
        config = _Config(
            {
                "enabled": False,
                "provider": "subprocess_stdio",
                "command": [
                    "${PYTHON_EXECUTABLE}",
                    "${WORKSPACE_ROOT}/scripts/custom_response_rewriter.py",
                ],
            }
        )
        config.workspace_root = Path("C:/workspace/NLP")
        rewriter = ResponseRewriter(config_manager=config)

        resolved = rewriter._resolve_command(config.response_rewriter_config["command"])

        self.assertEqual(resolved[0], sys.executable)
        self.assertTrue(resolved[1].endswith("scripts/custom_response_rewriter.py"))

    def test_persistent_subprocess_backend_reuses_same_process_across_rewrites(self):
        self._write_backend(
            """
            import json
            import os
            import sys

            counter = 0
            for raw_line in sys.stdin:
                line = raw_line.strip()
                if not line:
                    continue
                counter += 1
                payload = json.loads(line)
                text = f"{os.getpid()}:{counter}:{payload['input']['response_text']}"
                sys.stdout.write(json.dumps({"text": text}, ensure_ascii=False) + "\\n")
                sys.stdout.flush()
            """
        )
        rewriter = ResponseRewriter(
            config_manager=self._build_config(provider="persistent_subprocess_jsonl")
        )
        self.addCleanup(getattr(rewriter.plugin, "close", lambda: None))

        first = rewriter.rewrite(
            {"analysis": {"intent": "GENERAL"}, "response": {}},
            "一回目です。",
        )
        second = rewriter.rewrite(
            {"analysis": {"intent": "GENERAL"}, "response": {}},
            "二回目です。",
        )

        first_pid, first_count, first_text = first.split(":", 2)
        second_pid, second_count, second_text = second.split(":", 2)
        self.assertEqual(first_pid, second_pid)
        self.assertEqual(first_count, "1")
        self.assertEqual(second_count, "2")
        self.assertEqual(first_text, "一回目です。")
        self.assertEqual(second_text, "二回目です。")

    def test_openai_compatible_http_backend_rewrites_text(self):
        captured = {}

        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body_length = int(self.headers.get("Content-Length", "0"))
                captured["body"] = json.loads(self.rfile.read(body_length).decode("utf-8"))
                response = {
                    "choices": [
                        {
                            "message": {
                                "content": "元の応答です。 （llama.cpp自然化）。"
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

        rewriter = ResponseRewriter(
            config_manager=self._build_config(
                provider="openai_compatible_http",
                endpoint_url=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                model="local-llama",
                max_new_tokens=24,
            )
        )

        result = rewriter.rewrite(
            {"analysis": {"intent": "GENERAL"}, "response": {}},
            "元の応答です。",
        )

        self.assertEqual(result, "元の応答です。 （llama.cpp自然化）。")
        self.assertEqual(captured["body"]["model"], "local-llama")
        self.assertEqual(captured["body"]["max_tokens"], 24)
        self.assertFalse(captured["body"]["stream"])
        self.assertEqual(captured["body"]["messages"][0]["role"], "system")

    def test_openai_compatible_http_backend_falls_back_when_it_echoes_original_user_text(self):
        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                response = {
                    "choices": [
                        {
                            "message": {
                                "content": "進捗を教えて"
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

        rewriter = ResponseRewriter(
            config_manager=self._build_config(
                provider="openai_compatible_http",
                endpoint_url=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                model="local-llama",
                max_new_tokens=24,
            )
        )

        result = rewriter.rewrite(
            {
                "analysis": {"intent": "GENERAL"},
                "original_text": "進捗を教えて",
                "response": {},
            },
            "処理を開始しました。完了まで少々お待ちください。現在、処理を進めています。",
        )

        self.assertEqual(
            result,
            "処理を開始しました。完了まで少々お待ちください。現在、処理を進めています。",
        )

    def test_openai_compatible_http_backend_falls_back_when_sentence_ending_breaks(self):
        class _Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                response = {
                    "choices": [
                        {
                            "message": {
                                "content": "天気の話題ですね。私は今の天気を直接知ることはできませんが、お話し相手にはなれますが、あなたがどこで"
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

        rewriter = ResponseRewriter(
            config_manager=self._build_config(
                provider="openai_compatible_http",
                endpoint_url=f"http://127.0.0.1:{server.server_port}/v1/chat/completions",
                model="local-llama",
                max_new_tokens=24,
            )
        )

        result = rewriter.rewrite(
            {"analysis": {"intent": "WEATHER"}, "response": {}},
            "天気の話題ですね。私は今の天気を直接知ることはできませんが、お話し相手にはなれますよ。",
        )

        self.assertEqual(
            result,
            "天気の話題ですね。私は今の天気を直接知ることはできませんが、お話し相手にはなれますよ。",
        )


if __name__ == "__main__":
    unittest.main()
