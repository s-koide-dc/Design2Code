import unittest
import os
import shutil
from unittest.mock import MagicMock
from src.action_executor.action_executor import ActionExecutor

class TestSecurityBoundaries(unittest.TestCase):
    def setUp(self):
        self.test_ws = os.path.abspath("security_test_workspace")
        if os.path.exists(self.test_ws):
            shutil.rmtree(self.test_ws)
        os.makedirs(self.test_ws)
        self.mock_log = MagicMock()
        self.executor = ActionExecutor(log_manager=self.mock_log)
        self.executor.workspace_root = self.test_ws

    def tearDown(self):
        if os.path.exists(self.test_ws):
            shutil.rmtree(self.test_ws)

    def test_safe_path_resolution(self):
        """Test that normal paths inside workspace resolve correctly."""
        path = self.executor._safe_join("test.txt")
        expected = os.path.join(self.test_ws, "test.txt")
        self.assertEqual(path, expected)

        path = self.executor._safe_join("dir/subdir/file.log")
        expected = os.path.join(self.test_ws, "dir", "subdir", "file.log")
        self.assertEqual(path, expected)

    def test_traversal_prevention(self):
        """Test that '..' traversal components are blocked."""
        # Simple traversal
        self.assertIsNone(self.executor._safe_join("../outside.txt"))
        
        # Complex traversal trying to come back in
        # (Should be allowed if it stays within, but abspath resolves it)
        path = self.executor._safe_join("dir/../../in_root.txt")
        self.assertIsNone(path, "Traversal that goes above root should be blocked even if it tries to return.")

    def test_absolute_path_prevention(self):
        """Test that absolute paths are treated as relative to root or blocked if they point outside."""
        if os.name == 'nt':
            # Windows absolute path
            self.assertIsNone(self.executor._safe_join("C:\\Windows\\System32\\cmd.exe"))
            self.assertIsNone(self.executor._safe_join("D:/data"))
        else:
            # Unix absolute path
            self.assertIsNone(self.executor._safe_join("/etc/passwd"))

    def test_edge_case_dots(self):
        """Test paths with multiple dots or tricky naming."""
        self.assertIsNotNone(self.executor._safe_join("...file.txt")) # Valid filename
        self.assertIsNone(self.executor._safe_join("/.../etc/passwd"))
        
    def test_null_byte_injection(self):
        """Test for null byte injection."""
        self.assertIsNone(self.executor._safe_join("test.txt\0.js"))

if __name__ == "__main__":
    unittest.main()
