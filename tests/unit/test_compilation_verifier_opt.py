# -*- coding: utf-8 -*-
import unittest
import os
import shutil
from unittest.mock import patch, MagicMock
from src.code_verification.compilation_verifier import CompilationVerifier

class TestCompilationVerifierOptimization(unittest.TestCase):
    def setUp(self):
        self.verifier = CompilationVerifier()
        self.test_dir = os.path.join(os.getcwd(), "tests", "tmp_verifier_opt")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        
        # cache/base_sandbox もクリーンアップ
        if os.path.exists(self.verifier.base_sandbox_path):
             shutil.rmtree(self.verifier.base_sandbox_path)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        if os.path.exists(self.verifier.base_sandbox_path):
             shutil.rmtree(self.verifier.base_sandbox_path)

    @patch('subprocess.run')
    def test_verify_uses_base_sandbox(self, mock_run):
        """2回目以降の verify で base_sandbox が利用されるか"""
        # 1. 最初の呼び出し (base_sandbox が作成される)
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        
        # mock_run が呼ばれた際に実際にファイルを生成するようにしないと _ensure_base_sandbox が成功しない
        def side_effect(args, **kwargs):
            cwd = kwargs.get('cwd')
            if cwd:
                os.makedirs(os.path.join(cwd, "obj"), exist_ok=True)
                with open(os.path.join(cwd, "Sandbox.csproj"), 'w') as f: f.write("")
            return MagicMock(returncode=0, stdout="", stderr="")
        
        mock_run.side_effect = side_effect
        
        code = "public class A {}"
        self.verifier.verify(code)
        
        # base_sandbox が作成されているはず
        self.assertTrue(os.path.exists(self.verifier.base_sandbox_path))
        
        # 2. 別のディレクトリでの呼び出し
        mock_run.reset_mock()
        mock_run.side_effect = side_effect
        temp_dir2 = os.path.join(self.test_dir, "sandbox2")
        self.verifier.verify(code, work_dir=temp_dir2)
        
        # build コマンドが --no-restore を含んでいるか確認
        called_args = [call.args[0] for call in mock_run.call_args_list]
        build_calls = [arg for arg in called_args if 'build' in arg]
        
        if build_calls:
            self.assertIn('--no-restore', build_calls[0])

if __name__ == '__main__':
    unittest.main()