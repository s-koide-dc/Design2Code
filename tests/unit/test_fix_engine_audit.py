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


    def test_logic_gap_without_structural_contract_requires_manual_review(self):
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
        self.assertEqual(suggestion.suggested_code, '')
        self.assertFalse(suggestion.auto_applicable)
        self.assertIn(
            'replacement_code',
            suggestion.impact_analysis['missing_requirements'],
        )
        self.assertEqual(
            suggestion.impact_analysis['recommended_action'],
            'inspect_manual_fix',
        )

    def test_logic_gap_with_complete_structural_contract_is_actionable(self):
        # 1. Arrange
        analysis_result = {
            'status': 'inconsistent',
            'findings': [
                {
                    'type': 'missing_step',
                    'step_id': 'step_3',
                    'step_text': 'Calculate tax',
                    'symbol_id': 'M:OrderService.CalculateTotal',
                    'start_line': 2,
                    'end_line': 5,
                    'replacement_code': (
                        'public decimal CalculateTotal(Order order) {\n'
                        '    return order.Items.Sum(i => i.Price) * 1.1m;\n'
                        '}'
                    ),
                    'validation_command': ['dotnet', 'test'],
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
        
        self.assertTrue(suggestion.auto_applicable)
        self.assertNotIn('TODO', suggestion.suggested_code)
        self.assertEqual(
            suggestion.symbol_id,
            'M:OrderService.CalculateTotal',
        )
        self.assertEqual(suggestion.line_number, 2)
        self.assertEqual(suggestion.end_line, 5)
        self.assertEqual(suggestion.validation_command, ['dotnet', 'test'])

    def test_arrange_fix_without_contract_requires_manual_review(self):
        """契約なしのMock Arrange修正は手動調査候補にする"""
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
        
        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion.type, 'manual_fix')
        self.assertFalse(suggestion.auto_applicable)
        self.assertEqual(suggestion.suggested_code, '')
        self.assertEqual(
            suggestion.impact_analysis['recommended_action'],
            'inspect_manual_fix',
        )

    def test_arrange_fix_with_contract_is_actionable(self):
        """構造化Arrange契約がある場合だけ適用可能にする"""
        analysis_result = {
            'fix_direction': 'fix_test_arrange',
            'arrange_edit': {
                'arrange_statement': 'mockRepo.Save(Arg.Any<User>()).Returns(5);',
                'insert_line': 5,
                'validation_command': ['dotnet', 'test'],
                'symbol_id': 'M:UserServiceTests.TestCreateUser',
            },
        }
        target_code = {
            'file': 'UserServiceTests.cs',
            'method': 'TestCreateUser',
            'current_implementation': """
        [Test]
        public void TestCreateUser() {
            var mockRepo = Substitute.For<IUserRepository>();
            var service = new UserService(mockRepo);
            var result = service.CreateUser(new User());
            Assert.AreEqual(5, result);
        }
        """
        }

        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)

        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion.type, 'test_arrange_fix')
        self.assertTrue(suggestion.auto_applicable)
        self.assertEqual(
            suggestion.suggested_code,
            'mockRepo.Save(Arg.Any<User>()).Returns(5);',
        )
        self.assertEqual(suggestion.line_number, 5)
        self.assertEqual(suggestion.symbol_id, 'M:UserServiceTests.TestCreateUser')
        self.assertEqual(suggestion.validation_command, ['dotnet', 'test'])

    def test_method_implementation_without_contract_requires_manual_review(self):
        analysis_result = {
            'fix_direction': 'implement_method_logic',
            'root_cause': 'method_returns_default_value',
            'analysis_summary': {
                'test_method': 'CalculatorTests.Add_ShouldReturnSum',
                'root_cause': 'method_returns_default_value'
            },
            'analysis_details': {
                'error_message': 'Expected: 5, Actual: 0'
            }
        }
        target_code = {
            'file': 'Calculator.cs',
            'method': 'Add',
            'current_implementation': 'public int Add(int a, int b) { return 0; }'
        }

        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)

        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion.type, 'manual_fix')
        self.assertFalse(suggestion.auto_applicable)
        self.assertEqual(suggestion.suggested_code, '')
        self.assertEqual(getattr(suggestion, 'target_file', None), 'Calculator.cs')
        self.assertIn('conversation_hint', suggestion.impact_analysis)
        self.assertIn('CalculatorTests.Add_ShouldReturnSum', suggestion.impact_analysis['conversation_hint'])
        self.assertIn('reason', suggestion.impact_analysis)
        self.assertIn('method_returns_default_value', suggestion.impact_analysis['reason'])
        self.assertEqual(suggestion.impact_analysis['recommended_action'], 'inspect_manual_fix')
        self.assertIn('CalculatorTests.Add_ShouldReturnSum', suggestion.impact_analysis['target_summary'])

    def test_method_implementation_with_contract_is_actionable(self):
        analysis_result = {
            'fix_direction': 'implement_method_logic',
            'replacement_code': 'public int Add(int a, int b) { return a + b; }',
            'symbol_id': 'M:Calculator.Add',
            'start_line': 3,
            'end_line': 5,
            'validation_command': ['dotnet', 'test'],
        }
        target_code = {
            'file': 'Calculator.cs',
            'method': 'Add',
            'current_implementation': 'public int Add(int a, int b) { return 0; }'
        }

        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)

        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion.type, 'method_implementation')
        self.assertTrue(suggestion.auto_applicable)
        self.assertEqual(
            suggestion.suggested_code,
            'public int Add(int a, int b) { return a + b; }',
        )
        self.assertEqual(suggestion.symbol_id, 'M:Calculator.Add')
        self.assertEqual(suggestion.line_number, 3)
        self.assertEqual(suggestion.end_line, 5)
        self.assertEqual(suggestion.validation_command, ['dotnet', 'test'])

    def test_syntax_fix_without_contract_requires_manual_review(self):
        analysis_result = {
            'fix_direction': 'fix_syntax_error',
            'analysis_details': {
                'error_message': "error CS0246: The type or namespace name 'T' could not be found",
            },
        }
        target_code = {
            'file': 'Generated.cs',
            'method': 'Create',
            'current_implementation': 'public T Create() { return default; }',
        }

        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)

        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion.type, 'manual_fix')
        self.assertFalse(suggestion.auto_applicable)
        self.assertEqual(suggestion.suggested_code, '')
        self.assertEqual(
            suggestion.impact_analysis['recommended_action'],
            'inspect_manual_fix',
        )

    def test_syntax_fix_with_contract_is_actionable(self):
        analysis_result = {
            'fix_direction': 'fix_syntax_error',
            'replacement_code': 'public object Create() { return default; }',
            'start_line': 1,
            'end_line': 1,
            'validation_command': ['dotnet', 'test'],
        }
        target_code = {
            'file': 'Generated.cs',
            'method': 'Create',
            'current_implementation': 'public T Create() { return default; }',
        }

        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)

        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion.type, 'syntax_fix')
        self.assertTrue(suggestion.auto_applicable)
        self.assertEqual(
            suggestion.suggested_code,
            'public object Create() { return default; }',
        )
        self.assertEqual(suggestion.line_number, 1)
        self.assertEqual(suggestion.end_line, 1)
        self.assertEqual(suggestion.validation_command, ['dotnet', 'test'])

    def test_null_check_without_contract_requires_manual_review(self):
        analysis_result = {
            'fix_direction': 'add_null_checks',
            'root_cause': 'null_reference',
        }
        target_code = {
            'file': 'UserService.cs',
            'method': 'Normalize',
            'current_implementation': 'return user.Name.Trim();',
        }

        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)

        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion.type, 'manual_fix')
        self.assertFalse(suggestion.auto_applicable)
        self.assertEqual(suggestion.suggested_code, '')
        self.assertEqual(
            suggestion.impact_analysis['recommended_action'],
            'inspect_manual_fix',
        )
        self.assertEqual(
            suggestion.impact_analysis['contract_reason'],
            'missing_structural_edit_contract',
        )

    def test_null_check_with_contract_is_actionable(self):
        analysis_result = {
            'fix_direction': 'add_null_validation',
            'null_check_edit': {
                'replacement_code': (
                    'public string Normalize(User user) {\n'
                    '    ArgumentNullException.ThrowIfNull(user);\n'
                    '    return user.Name.Trim();\n'
                    '}'
                ),
                'symbol_id': 'M:UserService.Normalize',
                'start_line': 10,
                'end_line': 12,
                'validation_command': ['dotnet', 'test'],
            },
        }
        target_code = {
            'file': 'UserService.cs',
            'method': 'Normalize',
            'current_implementation': 'return user.Name.Trim();',
        }

        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)

        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion.type, 'null_validation')
        self.assertTrue(suggestion.auto_applicable)
        self.assertIn('ThrowIfNull', suggestion.suggested_code)
        self.assertEqual(suggestion.symbol_id, 'M:UserService.Normalize')
        self.assertEqual(suggestion.line_number, 10)
        self.assertEqual(suggestion.end_line, 12)
        self.assertEqual(suggestion.validation_command, ['dotnet', 'test'])

    def test_calculation_fix_without_contract_requires_manual_review(self):
        analysis_result = {
            'fix_direction': 'fix_calculation_logic',
            'root_cause': 'calculation_logic_error',
        }
        target_code = {
            'file': 'Calculator.cs',
            'method': 'Total',
            'current_implementation': 'return price;',
        }

        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)

        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion.type, 'manual_fix')
        self.assertFalse(suggestion.auto_applicable)
        self.assertEqual(suggestion.suggested_code, '')
        self.assertEqual(
            suggestion.impact_analysis['recommended_action'],
            'inspect_manual_fix',
        )
        self.assertEqual(
            suggestion.impact_analysis['contract_reason'],
            'missing_structural_edit_contract',
        )

    def test_calculation_fix_with_contract_is_actionable(self):
        analysis_result = {
            'fix_direction': 'fix_calculation_logic',
            'calculation_edit': {
                'replacement_code': (
                    'public decimal Total(decimal price, decimal taxRate) {\n'
                    '    return price * (1 + taxRate);\n'
                    '}'
                ),
                'symbol_id': 'M:Calculator.Total',
                'start_line': 4,
                'end_line': 6,
                'validation_command': ['dotnet', 'test'],
            },
        }
        target_code = {
            'file': 'Calculator.cs',
            'method': 'Total',
            'current_implementation': 'return price;',
        }

        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)

        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion.type, 'calculation_fix')
        self.assertTrue(suggestion.auto_applicable)
        self.assertIn('taxRate', suggestion.suggested_code)
        self.assertEqual(suggestion.symbol_id, 'M:Calculator.Total')
        self.assertEqual(suggestion.line_number, 4)
        self.assertEqual(suggestion.end_line, 6)
        self.assertEqual(suggestion.validation_command, ['dotnet', 'test'])

    def test_numeric_mismatch_without_contract_requires_manual_review(self):
        analysis_result = {
            'status': 'inconsistent',
            'findings': [
                {
                    'type': 'logic_value_mismatch',
                    'detail': "数値 '0.9' (threshold) が設計と異なります。",
                }
            ],
        }
        target_code = {
            'file': 'Rules.cs',
            'method': 'Apply',
            'current_implementation': 'threshold = 0.8;',
        }

        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)

        self.assertGreaterEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion.type, 'manual_fix')
        self.assertFalse(suggestion.auto_applicable)
        self.assertEqual(suggestion.suggested_code, '')
        self.assertEqual(
            suggestion.impact_analysis['recommended_action'],
            'inspect_manual_fix',
        )

    def test_parameter_fix_without_contract_requires_manual_review(self):
        analysis_result = {
            'status': 'inconsistent',
            'findings': [
                {
                    'type': 'missing_parameter',
                    'detail': "パラメータ 'amount' が不足しています。",
                }
            ],
        }
        target_code = {
            'file': 'Rules.cs',
            'method': 'Apply',
            'current_implementation': 'public void Apply() { }',
        }

        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)

        self.assertEqual(len(suggestions), 1)
        suggestion = suggestions[0]
        self.assertEqual(suggestion.type, 'manual_fix')
        self.assertFalse(suggestion.auto_applicable)
        self.assertEqual(suggestion.suggested_code, '')
        self.assertEqual(
            suggestion.impact_analysis['recommended_action'],
            'inspect_manual_fix',
        )

    def test_backport_without_contract_is_not_generated(self):
        analysis_result = {
            'status': 'inconsistent',
            'design_path': 'Rules.design.md',
            'findings': [
                {
                    'type': 'logic_value_mismatch',
                    'detail': "ステップ 2 の数値 '0.9' がコードと異なります。",
                }
            ],
        }
        target_code = {
            'file': 'Rules.cs',
            'method': 'Apply',
            'current_implementation': 'threshold = 0.8;',
        }

        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)

        self.assertFalse(
            any(suggestion.type == 'backport_to_design' for suggestion in suggestions)
        )

    def test_backport_with_contract_is_generated(self):
        analysis_result = {
            'status': 'inconsistent',
            'design_path': 'Rules.design.md',
            'findings': [
                {
                    'type': 'logic_value_mismatch',
                    'backport_content': '2. Use threshold 0.8 from implementation.',
                    'step_idx': 2,
                }
            ],
        }
        target_code = {
            'file': 'Rules.cs',
            'method': 'Apply',
            'current_implementation': 'threshold = 0.8;',
        }

        suggestions = self.engine.generate_fix_suggestions(analysis_result, target_code)
        backports = [
            suggestion
            for suggestion in suggestions
            if suggestion.type == 'backport_to_design'
        ]

        self.assertEqual(len(backports), 1)
        self.assertEqual(
            backports[0].suggested_code,
            '2. Use threshold 0.8 from implementation.',
        )
        self.assertEqual(backports[0].impact_analysis['step_idx'], 2)
        self.assertEqual(
            backports[0].impact_analysis['design_file'],
            'Rules.design.md',
        )

if __name__ == '__main__':
    unittest.main()
