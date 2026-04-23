import unittest
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.advanced_tdd.dummy_factory import DummyDataFactory
from src.advanced_tdd.models import TestFailure

class TestDummyFactoryLearning(unittest.TestCase):
    def setUp(self):
        self.factory = DummyDataFactory()

    def test_default_instantiation(self):
        # プリミティブ
        self.assertEqual(self.factory.generate_instantiation('int'), '0')
        self.assertEqual(self.factory.generate_instantiation('string'), '""')
        # 未知のクラス
        self.assertEqual(self.factory.generate_instantiation('User'), 'new User()')

    def test_learning_loop_from_null_ref(self):
        # NullReferenceException を模した失敗データ
        # メッセージに "user.Profile is null" を含む
        failure = TestFailure(
            test_file="UserTests.cs",
            test_method="Test_ProcessUser",
            error_type="runtime_error",
            error_message="System.NullReferenceException: Object reference not set to an instance of an object. user.Profile is null",
            stack_trace="..."
        )
        
        # 学習前
        self.assertEqual(self.factory.generate_instantiation('User'), 'new User()')
        
        # 学習
        self.factory.learn_from_failure(failure)
        
        # 学習後: Profile プロパティが初期化子に含まれる
        result = self.factory.generate_instantiation('User')
        self.assertIn('new User {', result)
        self.assertIn('Profile = new Profile()', result)

    def test_learning_loop_from_missing_field(self):
        # MissingFieldException を模した失敗データ
        failure = TestFailure(
            test_file="OrderTests.cs",
            test_method="Test_CreateOrder",
            error_type="runtime_error",
            error_message="Property 'Amount' not found on type 'Order'",
            stack_trace="..."
        )
        
        # 学習
        self.factory.learn_from_failure(failure)
        
        # 学習後: Amount プロパティが含まれる (guess_value_for_prop により 10 と推測される)
        result = self.factory.generate_instantiation('Order')
        self.assertIn('Amount = 10', result)

    def test_multiple_properties_learning(self):
        # 複数のエラーから複数のプロパティを学習
        f1 = TestFailure(test_file="f1", test_method="m1", error_type="e1", 
                         error_message="user.Name is null", stack_trace="")
        f2 = TestFailure(test_file="f2", test_method="m2", error_type="e2", 
                         error_message="user.Age is null", stack_trace="")
        
        self.factory.learn_from_failure(f1)
        self.factory.learn_from_failure(f2)
        
        result = self.factory.generate_instantiation('User')
        # 両方のプロパティが含まれる (セマンティックな値)
        self.assertIn('Name = "Test User"', result)
        self.assertIn('Age = 25', result)

    def test_semantic_data_generation(self):
        # プロパティ名に基づいたセマンティックな値の生成
        self.assertEqual(self.factory._guess_value_for_prop('Email'), '"test@example.com"')
        self.assertEqual(self.factory._guess_value_for_prop('FirstName'), '"John"')
        self.assertEqual(self.factory._guess_value_for_prop('CreatedAt'), 'DateTime.Now')
        self.assertEqual(self.factory._guess_value_for_prop('Price'), '1000')

if __name__ == '__main__':
    unittest.main()
