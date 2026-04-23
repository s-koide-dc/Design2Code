# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock
from src.safety.safety_policy_validator import SafetyPolicyValidator, SafetyCheckResult, SafetyCheckStatus, RiskLevel

class TestSafetyPolicyValidator(unittest.TestCase):
    def setUp(self):
        self.mock_action_executor = MagicMock()
        self.mock_action_executor.safe_commands = ["git", "ls", "dir", "echo"]
        self.validator = SafetyPolicyValidator(self.mock_action_executor)

    def test_safe_action(self):
        result = self.validator.validate_action("_read_file", {"filename": "test.txt"}, "FILE_READ")
        self.assertEqual(result.status, SafetyCheckStatus.OK)
        self.assertEqual(result.risk_level, RiskLevel.LOW)

    def test_destructive_action(self):
        result = self.validator.validate_action("_delete_file", {"filename": "test.txt"}, "FILE_DELETE")
        self.assertEqual(result.status, SafetyCheckStatus.OK)
        # Should be High Risk
        self.assertEqual(result.risk_level, RiskLevel.HIGH)
        self.assertIn("破壊的な変更", result.message)

    def test_cautionary_action(self):
        result = self.validator.validate_action("_append_file", {"filename": "test.txt", "content": "add"}, "FILE_APPEND")
        self.assertEqual(result.status, SafetyCheckStatus.OK)
        # Should be High Risk now
        self.assertEqual(result.risk_level, RiskLevel.HIGH)

    def test_allowed_cmd_run(self):
        result = self.validator.validate_action("_run_command", {"command": "ls -l"}, "CMD_RUN")
        self.assertEqual(result.status, SafetyCheckStatus.OK)
        # CMD_RUN is High Risk
        self.assertEqual(result.risk_level, RiskLevel.HIGH)

    def test_blocked_cmd_run(self):
        # cmd_run with an unlisted command should be BLOCKED
        parameters = {"command": "rm -rf /"}
        result = self.validator.validate_action("_run_command", parameters, intent="CMD_RUN")
        self.assertEqual(result.status, SafetyCheckStatus.BLOCK)
        self.assertIn("許可されていません", result.message)

    def test_missing_command_param(self):
        result = self.validator.validate_action("_run_command", {}, "CMD_RUN")
        self.assertEqual(result.status, SafetyCheckStatus.BLOCK)

if __name__ == '__main__':
    unittest.main()
