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

    def test_unstructured_failure_does_not_create_type_rules(self):
        failure = TestFailure(
            test_file="UserTests.cs",
            test_method="Test_ProcessUser",
            error_type="runtime_error",
            error_message="System.NullReferenceException: Object reference not set to an instance of an object. user.Profile is null",
            stack_trace="..."
        )
        
        learned = self.factory.learn_from_failure(failure)

        self.assertFalse(learned)
        self.assertEqual(self.factory.generate_instantiation('User'), 'new User()')

    def test_register_property_uses_resolved_numeric_type(self):
        self.assertTrue(
            self.factory.register_property("Order", "Amount", "decimal")
        )
        result = self.factory.generate_instantiation('Order')
        self.assertIn('Amount = 0.0m', result)

    def test_multiple_structured_properties(self):
        self.factory.register_property("User", "Name", "System.String")
        self.factory.register_property("User", "Age", "System.Int32")
        result = self.factory.generate_instantiation('User')
        self.assertIn('Name = ""', result)
        self.assertIn('Age = 0', result)

    def test_reference_and_collection_defaults_are_type_driven(self):
        self.assertEqual(
            self.factory._default_for_type("Example.Profile"),
            "new Profile()",
        )
        self.assertEqual(
            self.factory._default_for_type("IEnumerable<string>"),
            "new System.Collections.Generic.List<string>()",
        )

    def test_register_accessed_properties_uses_roslyn_symbol_ids(self):
        analysis_results = {
            "manifest": {
                "objects": [
                    {"id": "type-1", "fullName": "Example.DataItem"}
                ]
            },
            "details_by_id": {
                "type-1": {
                    "properties": [
                        {
                            "id": "prop-value",
                            "name": "Value",
                            "type": "System.String",
                        },
                        {
                            "id": "prop-count",
                            "name": "Count",
                            "type": "System.Int32",
                        },
                    ]
                }
            },
        }
        factory = DummyDataFactory(analysis_results=analysis_results)

        registered = factory.register_accessed_properties(
            "DataItem",
            ["prop-value"],
        )

        self.assertEqual(registered, 1)
        self.assertEqual(
            factory.generate_instantiation("DataItem"),
            'new DataItem { Value = "" }',
        )

if __name__ == '__main__':
    unittest.main()
