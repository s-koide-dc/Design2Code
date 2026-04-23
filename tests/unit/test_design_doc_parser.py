import unittest
import sys
import os
from pathlib import Path

# Adjust path to include src
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.design_doc_parser import DesignDocParser

class TestDesignDocParser(unittest.TestCase):
    def setUp(self):
        self.parser = DesignDocParser()

    def test_parse_content_basic(self):
        """Test parsing a controlled markdown string."""
        sample_md = """
# TestModule
## 1. Purpose
This is a test module.
## 2. Structured Specification
### Input
- **Description**: Target `id` and `name`.
- **Type/Format**: string, string
### Output
- **Description**: Resulting `data`.
### Core Logic
1. Step One
2. Step Two
### Test Cases
- **Scenario**: Happy Path
- **Input**: valid
- **Expected**: success
"""
        result = self.parser.parse_content(sample_md)
        
        self.assertEqual(result["module_name"], "TestModule")
        self.assertIn("test module", result["purpose"])
        self.assertIn("id", result["specification"]["input"]["description"])
        self.assertEqual(len(result["specification"]["core_logic"]), 2)
        self.assertEqual(result["test_cases"][0]["scenario"], "Happy Path")

if __name__ == "__main__":
    unittest.main()

