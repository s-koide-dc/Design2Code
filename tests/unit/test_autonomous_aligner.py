import unittest
from pathlib import Path
import os
import sys

# Add project root to sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.autonomous_aligner.autonomous_aligner import AutonomousAligner

class TestAutonomousAligner(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/temp_align_test")
        self.test_dir.mkdir(exist_ok=True)
        self.aligner = AutonomousAligner(str(project_root))

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_align_module_logic_gap(self):
        # 1. Arrange: テスト用の設計書とソースファイルを作成
        design_content = """# Mock Module Design Document
## 1. Purpose
Test logic gap alignment.
## 2. Structured Specification
### Core Logic
1. Initialize system.
2. Perform complex calculation.
3. Save results.
"""
        source_content = """
public class MockModule {
    public void MockFunction() {
        Console.WriteLine("Initializing...");
        // missing step 2
        Console.WriteLine("Saving results...");
    }
}
"""
        design_path = self.test_dir / "mock_mod.design.md"
        source_path = self.test_dir / "mock_mod.cs"
        
        with open(design_path, "w", encoding="utf-8") as f: f.write(design_content)
        with open(source_path, "w", encoding="utf-8") as f: f.write(source_content)

        # 2. Act
        result = self.aligner.align_module(design_path)

        # 3. Assert
        self.assertIsNotNone(result)
        self.assertIn("Perform complex calculation", str(result.get("fixes_applied")))
        
        # ファイルが更新されているか確認
        with open(source_path, "r", encoding="utf-8") as f:
            updated_code = f.read()
        
        self.assertIn("// TODO: Implement Logic: Perform complex calculation", updated_code)

if __name__ == "__main__":
    unittest.main()
