import unittest
from pathlib import Path
import os
import sys

# Add project root to sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.autonomous_aligner.autonomous_aligner import AutonomousAligner

class TestAutonomousAlignerPython(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/temp_align_test_py")
        self.test_dir.mkdir(exist_ok=True)
        self.aligner = AutonomousAligner(str(project_root))

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_align_module_logic_gap_python(self):
        # 1. Arrange
        design_content = """# PyMock Module Design Document
## 1. Purpose
Test logic gap alignment for Python.
## 2. Structured Specification
### Core Logic
1. Validate input.
2. Calculate score.
"""
        source_content = """
def process_data(data):
    # Step 1
    if not data:
        return
    print("Processing...")
"""
        design_path = self.test_dir / "pymock_mod.design.md"
        source_path = self.test_dir / "pymock_mod.py"
        
        with open(design_path, "w", encoding="utf-8") as f: f.write(design_content)
        with open(source_path, "w", encoding="utf-8") as f: f.write(source_content)

        # 2. Act
        result = self.aligner.align_module(design_path)

        # 3. Assert
        self.assertIsNotNone(result)
        self.assertIn("Calculate score", str(result.get("fixes_applied")))
        
        with open(source_path, "r", encoding="utf-8") as f:
            updated_code = f.read()
        
        # print(updated_code) # Debug
        self.assertIn("# TODO: Implement Logic: Calculate score", updated_code)

if __name__ == "__main__":
    unittest.main()
