# -*- coding: utf-8 -*-
import unittest
from unittest.mock import patch

from src.response_rewriter.qwen_cpu_runner import (
    DEFAULT_MAX_NEW_TOKENS,
    build_messages,
    run_rewrite,
    _postprocess_rewrite_output,
)


class _FakeTensor:
    def __init__(self, shape):
        self.shape = shape


class _FakeTokenizer:
    def __init__(self):
        self.messages = None

    def apply_chat_template(self, messages, add_generation_prompt=True, tokenize=True, return_tensors="pt", return_dict=True):
        self.messages = messages
        return {"input_ids": _FakeTensor((1, 5))}

    def decode(self, tokens, skip_special_tokens=True):
        return "自然な応答です。"


class _FakeModel:
    def __init__(self):
        self.calls = []

    def generate(self, input_ids=None, max_new_tokens=0, do_sample=False, **kwargs):
        self.calls.append(
            {
                "inputs_shape": input_ids.shape,
                "max_new_tokens": max_new_tokens,
                "do_sample": do_sample,
            }
        )
        return [[1, 2, 3, 4, 5, 6, 7]]


class TestQwenCpuRunner(unittest.TestCase):
    def test_build_messages_includes_instruction_and_constraints(self):
        payload = {
            "instruction": "自然な日本語に整えてください。",
            "constraints": {
                "rewrite_style": "natural_japanese",
                "preserve_facts": True,
                "forbid_code_generation": True,
                "forbid_new_commands": True,
                "forbid_markdown_blocks": True,
            },
            "input": {
                "response_text": "元の応答です。",
                "original_text": "天気は？",
                "intent": "WEATHER",
                "dialogue_state": "",
                "task_name": "",
                "action_status": "",
            },
        }

        messages = build_messages(payload)

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("自然な日本語に整えてください。", messages[0]["content"])
        self.assertIn("original_text はユーザーの元発話", messages[0]["content"])
        self.assertIn("主語・話者・視点を変えてはいけません。", messages[0]["content"])
        self.assertIn("文の役割はそのまま保ってください。", messages[0]["content"])
        self.assertIn("forbid_code_generation: True", messages[0]["content"])
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("intent: WEATHER", messages[1]["content"])
        self.assertIn("response_text:\n元の応答です。", messages[1]["content"])
        self.assertIn("reference_user_text: 天気は？", messages[1]["content"])

    @patch("src.response_rewriter.qwen_cpu_runner._load_model_and_tokenizer")
    def test_run_rewrite_uses_cpu_generation_contract(self, mock_loader):
        fake_model = _FakeModel()
        fake_tokenizer = _FakeTokenizer()
        mock_loader.return_value = (fake_model, fake_tokenizer)

        payload = {
            "instruction": "自然な日本語に整えてください。",
            "constraints": {
                "rewrite_style": "natural_japanese",
                "preserve_facts": True,
                "forbid_code_generation": True,
                "forbid_new_commands": True,
                "forbid_markdown_blocks": True,
            },
            "input": {
                "response_text": "元の応答です。",
                "original_text": "こんにちは",
                "intent": "GREETING",
                "dialogue_state": "",
                "task_name": "",
                "action_status": "",
            },
        }

        result = run_rewrite(payload)

        self.assertEqual(result, "自然な応答です。")
        self.assertEqual(fake_model.calls[0]["max_new_tokens"], DEFAULT_MAX_NEW_TOKENS)
        self.assertFalse(fake_model.calls[0]["do_sample"])
        self.assertEqual(fake_tokenizer.messages[0]["role"], "system")

    def test_postprocess_rewrite_output_rejects_added_question(self):
        payload = {
            "input": {
                "response_text": "元の応答です。"
            }
        }

        result = _postprocess_rewrite_output(payload, "こんにちは、何しますか？")

        self.assertEqual(result, "元の応答です。")

    def test_postprocess_rewrite_output_keeps_minimal_rewrite(self):
        payload = {
            "input": {
                "response_text": "元の応答です。"
            }
        }

        result = _postprocess_rewrite_output(payload, "元の応答です。")

        self.assertEqual(result, "元の応答です。")

    def test_postprocess_rewrite_output_rejects_incomplete_sentence_ending(self):
        payload = {
            "input": {
                "response_text": "私は今の天気を直接知ることはできませんが、お話し相手にはなれますよ。"
            }
        }

        result = _postprocess_rewrite_output(
            payload,
            "私は今の天気を直接知ることはできませんが、お話し相手にはなれますが、あなたがどこで"
        )

        self.assertEqual(result, payload["input"]["response_text"])

    def test_postprocess_rewrite_output_rejects_echo_of_original_user_text(self):
        payload = {
            "input": {
                "response_text": "処理を開始しました。完了まで少々お待ちください。現在、処理を進めています。",
                "original_text": "進捗を教えて",
            }
        }

        result = _postprocess_rewrite_output(payload, "進捗を教えて")

        self.assertEqual(result, payload["input"]["response_text"])


if __name__ == "__main__":
    unittest.main()
