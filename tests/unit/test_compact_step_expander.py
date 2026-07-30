from __future__ import annotations

import unittest

from src.design_parser.compact_step_expander import expand_compact_steps


class TestCompactStepExpander(unittest.TestCase):
    def test_expands_supported_fetch_without_inference(self):
        content = """# Sample
### Core Logic
1. [step|FETCH|string|string|source=APP_MODE|source_kind=env] モードを取得する
2. [step|DISPLAY|string|void] 表示する
### Test Cases
"""

        expanded, errors = expand_compact_steps(content)

        self.assertEqual([], errors)
        self.assertIn("[ACTION|FETCH|string|string|IO|APP_MODE|env]", expanded)
        self.assertIn("[ACTION|DISPLAY|string|void|NONE]", expanded)

    def test_rejects_missing_external_source(self):
        content = """### Core Logic
1. [step|FETCH|string|string] 取得する
"""

        _expanded, errors = expand_compact_steps(content)

        self.assertEqual(1, len(errors))
        self.assertIn("requires source", errors[0].detail)

    def test_does_not_expand_outside_core_logic(self):
        content = """# [step|DISPLAY|string|void]
### Core Logic
1. [ACTION|DISPLAY|string|void|NONE] 表示する
"""

        expanded, errors = expand_compact_steps(content)

        self.assertEqual([], errors)
        self.assertIn("# [step|DISPLAY|string|void]", expanded)
