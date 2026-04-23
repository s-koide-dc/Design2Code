# -*- coding: utf-8 -*-
"""Call Pattern 推論のユニットテスト"""
import unittest
import importlib.util

# 循環インポート回避: compilation_verifier を先にロード
spec = importlib.util.find_spec("src.code_verification.compilation_verifier")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

from src.code_synthesis.autonomous_synthesizer import AutonomousSynthesizer


class TestCallPattern(unittest.TestCase):
    """_build_call_template のテスト"""

    def test_build_call_template_single_param(self):
        template = AutonomousSynthesizer._build_call_template(
            "Utils.StringHelper", "Tokenize", [{"name": "input", "type": "string"}]
        )
        self.assertEqual(template, "Utils.StringHelper.Tokenize({input})")

    def test_build_call_template_multi_param(self):
        template = AutonomousSynthesizer._build_call_template(
            "Common.IO.Logger", "WriteLogToFile",
            [{"name": "path", "type": "string"}, {"name": "message", "type": "string"}]
        )
        self.assertEqual(template, "Common.IO.Logger.WriteLogToFile({path}, {message})")

    def test_build_call_template_no_params(self):
        template = AutonomousSynthesizer._build_call_template(
            "Global", "GetConfig", []
        )
        self.assertEqual(template, "Global.GetConfig()")


if __name__ == "__main__":
    unittest.main()
