import unittest
import os
import shutil
from unittest.mock import MagicMock
from src.action_executor.action_executor import ActionExecutor

class TestDirectoryOperations(unittest.TestCase):
    def setUp(self):
        self.test_ws = os.path.abspath("dir_test_workspace")
        if os.path.exists(self.test_ws):
            shutil.rmtree(self.test_ws)
        os.makedirs(self.test_ws)
        
        self.mock_log = MagicMock()
        self.executor = ActionExecutor(log_manager=self.mock_log)
        self.executor.workspace_root = self.test_ws

    def tearDown(self):
        if os.path.exists(self.test_ws):
            shutil.rmtree(self.test_ws)

    def test_copy_directory_recursive(self):
        # Setup: Create a directory with files
        src_dir = os.path.join(self.test_ws, "src_dir")
        os.makedirs(src_dir)
        with open(os.path.join(src_dir, "file1.txt"), "w") as f:
            f.write("content1")
        
        dest_dir = "dest_dir"
        
        context = {"analysis": {"intent": "FILE_COPY"}}
        parameters = {"source_filename": "src_dir", "destination_filename": dest_dir}
        
        result_context = self.executor._copy_file(context, parameters)
        
        self.assertEqual(result_context["action_result"]["status"], "success")
        self.assertTrue(os.path.isdir(os.path.join(self.test_ws, dest_dir)))
        self.assertTrue(os.path.exists(os.path.join(self.test_ws, dest_dir, "file1.txt")))

    def test_delete_directory_recursive(self):
        # Setup: Create a directory with files
        target_dir = os.path.join(self.test_ws, "delete_me")
        os.makedirs(target_dir)
        with open(os.path.join(target_dir, "file1.txt"), "w") as f:
            f.write("content1")
            
        context = {"analysis": {"intent": "FILE_DELETE"}}
        parameters = {"filename": "delete_me"}
        
        result_context = self.executor._delete_file(context, parameters)
        
        self.assertEqual(result_context["action_result"]["status"], "success")
        self.assertFalse(os.path.exists(target_dir))

    def test_move_directory(self):
        # Setup: Create a directory with files
        src_dir = os.path.join(self.test_ws, "move_src")
        os.makedirs(src_dir)
        with open(os.path.join(src_dir, "file1.txt"), "w") as f:
            f.write("content1")
            
        dest_dir = "move_dest"
        
        context = {"analysis": {"intent": "FILE_MOVE"}}
        parameters = {"source_filename": "move_src", "destination_filename": dest_dir}
        
        result_context = self.executor._move_file(context, parameters)
        
        self.assertEqual(result_context["action_result"]["status"], "success")
        self.assertFalse(os.path.exists(src_dir))
        self.assertTrue(os.path.isdir(os.path.join(self.test_ws, dest_dir)))
        self.assertTrue(os.path.exists(os.path.join(self.test_ws, dest_dir, "file1.txt")))

if __name__ == "__main__":
    unittest.main()
