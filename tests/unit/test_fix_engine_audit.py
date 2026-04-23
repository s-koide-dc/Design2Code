import unittest
from unittest.mock import MagicMock
import sys
import os
import tempfile
import json
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.advanced_tdd.fix_engine import CodeFixSuggestionEngine

class TestFixEngineAudit(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.test_dir.name)
        
        # Create dummy SUT and Test files for Arrange fix test
        self.sut_file = "UserService.cs"
        self.test_file = "UserServiceTests.cs"
        
        with open(self.sut_file, 'w', encoding='utf-8') as f:
            f.write("""
            public class UserService { 
                private IUserRepository _repo;
                public int CreateUser(User u) { 
                    return _repo.Save(u); 
                } 
            }
            """)
            
        with open(self.test_file, 'w', encoding='utf-8') as f:
            f.write("[Test] public void TestCreateUser() { }")

        self.engine = CodeFixSuggestionEngine(config={})

    def tearDown(self):
        os.chdir(self.old_cwd)
        self.test_dir.cleanup()


    def test_logic_gap_fix_generation(self):
        # 1. Arrange
        analysis_result = {
            'status': 'inconsistent',
            'findings': [
                {
                    'type': 'logic_gap',
                    'detail': "Core Logic ステップ 2 ('Validate user input') に関連するキーワード (validate, input) がモジュール内のどのファイルにも見当たりません。"
                }
            ]
        }
        
        target_code = {
            'file': 'UserService.cs',
            'method': 'CreateUser',
            'current_implementation': """
public void CreateUser(User user) {
    _repository.Save(user);
}
"""
        }
        
        # 2. Act
        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)
        
        # 3. Assert
        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        
        self.assertEqual(suggestion.type, 'logic_gap_fix')
        self.assertIn('Validate user input', suggestion.description)
        self.assertIn('// TODO: Implement Logic: Validate user input', suggestion.suggested_code)
        
        # 生成されたコードの構造確認 (末尾に追加されているはず)
        expected_code = """
public void CreateUser(User user) {
    _repository.Save(user);
    // TODO: Implement Logic: Validate user input
}"""
        # 空白の違いを無視して比較
        self.assertEqual(suggestion.suggested_code.strip(), expected_code.strip())

    def test_logic_gap_fix_with_return(self):
        # 1. Arrange
        analysis_result = {
            'status': 'inconsistent',
            'findings': [
                {
                    'type': 'logic_gap',
                    'detail': "Core Logic ステップ 3 ('Calculate tax') に関連する..."
                }
            ]
        }
        
        target_code = {
            'file': 'OrderService.cs',
            'method': 'CalculateTotal',
            'current_implementation': """
public decimal CalculateTotal(Order order) {
    var subtotal = order.Items.Sum(i => i.Price);
    return subtotal;
}
"""
        }
        
        # 2. Act
        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)
        
        # 3. Assert
        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        
        self.assertIn('Calculate tax', suggestion.suggested_code)
        # return の前に挿入されているか
        self.assertIn('// TODO: Implement Logic: Calculate tax', suggestion.suggested_code)
        self.assertTrue(suggestion.suggested_code.index('// TODO') < suggestion.suggested_code.index('return subtotal'))

    def test_arrange_fix_generation(self):
        """Mock Arrange修正（戻り値設定）のテスト"""
        # 1. Arrange
        analysis_result = {
            'fix_direction': 'fix_test_arrange',
            'analysis_details': {
                'error_message': 'Expected: 5 But was: 0',
                'stack_trace_analysis': {
                    'file_locations': [
                        {'file': 'UserServiceTests.cs', 'line': 10},
                        {'file': 'UserService.cs', 'line': 5}
                    ],
                    'test_context': {
                        'test_method': 'TestCreateUser'
                    }
                }
            }
        }
        
        target_code = {
            'file': 'UserServiceTests.cs',
            'method': 'TestCreateUser',
            'current_implementation': """
        [Test]
        public void TestCreateUser() {
            var mockRepo = new Mock<IUserRepository>();
            mockRepo.Setup(r => r.Save(It.IsAny<User>())); 
            var service = new UserService(mockRepo.Object);
            var result = service.CreateUser(new User());
            Assert.AreEqual(5, result);
        }
        """
        }
        
        # 2. Act
        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)
        
        # 3. Assert
        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion.type, 'test_arrange_fix')
        # Returns() が追加されていることを確認 (簡易的なチェック)
        # 内部で NSubstitute (Returns) 形式がデフォルトになっている可能性があるため、確認
        self.assertTrue('Returns' in suggestion.suggested_code)

if __name__ == '__main__':
    unittest.main()
