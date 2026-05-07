import unittest
import sys
import os

# Add the scripts directory to the path so we can import the module
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
scripts_dir = os.path.join(base_dir, "scripts")
sys.path.append(scripts_dir)

from generate_ir_case_summary import parse_case_file

class TestGenerateIrCaseSummary(unittest.TestCase):
    def test_parse_case_file_valid(self):
        content = """# Case 01: StdinToStdoutTransform
Some introductory text.

## Source Scenario
- Scenario: `scenarios/StdinToStdoutTransform.design.md`
- Benchmark role: 最小の直列変換ケース

## Target Meaning Elements
- source_kind=`stdin`

## Expected Structure Summary
- 標準入力から 1 行取得する

## Failure Mapping
- Primary: Intent Drift
- Secondary: Under-Spec Capture
"""
        result = parse_case_file(content)
        self.assertEqual(result["case_id"], "01")
        self.assertEqual(result["title"], "StdinToStdoutTransform")
        self.assertEqual(result["benchmark_role"], "最小の直列変換ケース")
        self.assertEqual(result["primary"], "Intent Drift")
        self.assertEqual(result["secondary"], "Under-Spec Capture")

    def test_parse_case_file_missing_fields(self):
        content = """# Case 18: Check Provenance
Some introductory text.

## Source Scenario
- Scenario: Some scenario

## Failure Mapping
- Primary: none
"""
        result = parse_case_file(content)
        self.assertEqual(result["case_id"], "18")
        self.assertEqual(result["title"], "Check Provenance")
        self.assertEqual(result["benchmark_role"], "")
        self.assertEqual(result["primary"], "none")
        self.assertEqual(result["secondary"], "")

if __name__ == '__main__':
    unittest.main()
