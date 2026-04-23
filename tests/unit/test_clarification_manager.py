import unittest
import os
import json
import shutil # Import shutil
from unittest.mock import MagicMock, patch

# Assuming ClarificationManager is in src.clarification_manager.clarification_manager
# and ActionExecutor is in src.action_executor.action_executor
from src.clarification_manager.clarification_manager import ClarificationManager
from src.action_executor.action_executor import ActionExecutor

# Mock the log_manager as it's not the focus of this unit test
mock_log_manager = MagicMock()

class TestClarificationManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a dummy knowledge_base.json for testing clarification templates
        cls.test_resources_dir = "test_resources"
        os.makedirs(cls.test_resources_dir, exist_ok=True)
        cls.kb_path = os.path.join(cls.test_resources_dir, "knowledge_base.json")
        with open(cls.kb_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "clarification_templates": {
                        "default_clarification": "申し訳ありませんが、意図が明確ではありません。もう少し詳しく教えていただけますか？",
                        "ambiguous_intent": "おっしゃる意図は'{intent1}'（信頼度:{conf1:.2f}）でしょうか、それとも'{intent2}'（信頼度:{conf2:.2f}）でしょうか？",
                        "low_intent_confidence": "意図が明確ではありません。'{intent}'（信頼度:{conf:.2f}）でよろしいでしょうか？",
                        "low_entity_confidence": "エンティティ'{entity_key}'（値:'{entity_value}'、信頼度:{conf:.2f}）が不明確です。よろしいでしょうか？",
                        "missing_entity": "{entity_key}が不足しています。教えていただけますか？",
                        "max_attempts_reached": "申し訳ありません。意図が特定できませんでした。必要な情報の一覧を提示しますので、手動で操作してください。\n不足情報: {missing_info}"
                    }
                }
            , f, ensure_ascii=False, indent=2)
        
        # Patch os.path.join to point to our test resources dir for knowledge base loading
        cls.original_os_path_join = os.path.join # Store the original
        cls.patcher = patch('src.clarification_manager.clarification_manager.os.path.join', side_effect=cls._mock_os_path_join)
        cls.mock_join = cls.patcher.start()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_resources_dir):
            shutil.rmtree(cls.test_resources_dir) # Remove the directory and all its contents
        cls.patcher.stop() # This should happen regardless

    @staticmethod
    def _mock_os_path_join(*args):
        if 'knowledge_base.json' in args:
            return TestClarificationManager.kb_path
        # Call the stored original os.path.join
        return TestClarificationManager.original_os_path_join(*args)

    def setUp(self):
        self.mock_action_executor = MagicMock(spec=ActionExecutor)
        # Configure mock ActionExecutor to return required entities
        self.mock_action_executor.get_required_entities_for_intent.side_effect = \
            lambda intent: {
                "FILE_CREATE": ["filename", "content"],
                "FILE_EDIT": ["filename", "content"],
                "FILE_READ": ["filename"],
                "CMD_RUN": ["command"],
                "AMBIGUOUS_ACTION": []
            }.get(intent, [])
        
        self.cm = ClarificationManager(
            action_executor=self.mock_action_executor,
            log_manager=mock_log_manager,
            clarification_thresholds={"intent": 0.7, "entity": 0.7},
            max_clarification_attempts=3
        )

    def test_low_intent_confidence(self):
        context = {
            "original_text": "曖昧な指示",
            "analysis": {"intent": "AMBIGUOUS_ACTION", "intent_confidence": 0.6},
        }

        result = self.cm.manage_clarification(context)
        self.assertTrue(result["clarification_needed"])
        self.assertIn("意図が明確ではありません。", result["response"]["text"])
        self.assertIn("AMBIGUOUS_ACTION", result["response"]["text"])
        self.assertEqual(self.cm.clarification_history[hash(context["original_text"])], 1)

    def test_low_entity_confidence(self):
        context = {
            "original_text": "ファイル A を編集",
            "analysis": {
                "intent": "FILE_EDIT", "intent_confidence": 0.9,
                "entities": {"filename": {"value": "file A", "confidence": 0.6}}
            },
        }
        result = self.cm.manage_clarification(context)
        self.assertTrue(result["clarification_needed"])
        self.assertIn("エンティティ'filename'（値:'file A'、信頼度:0.60）が不明確です。", result["response"]["text"])
        self.assertEqual(self.cm.clarification_history[hash(context["original_text"])], 1)

    def test_missing_required_entity(self):
        context = {
            "original_text": "ファイルを作って",
            "analysis": {
                "intent": "FILE_CREATE", "intent_confidence": 0.9,
                "entities": {"filename": {"value": "new.txt", "confidence": 0.9}} # Content is missing
            },
        }
        result = self.cm.manage_clarification(context)
        self.assertTrue(result["clarification_needed"])
        self.assertIn("ファイルの内容を教えていただけますか？", result["response"]["text"])
        self.assertEqual(self.cm.clarification_history[hash(context["original_text"])], 1)

    def test_max_attempts_reached_for_missing_entity(self):
        # Test case for when max attempts are reached for a missing entity in a known intent
        original_text = "繰り返しのファイル作成指示"
        context = {
            "original_text": original_text,
            "analysis": {
                "intent": "FILE_CREATE", "intent_confidence": 0.9,
                "entities": {"filename": {"value": "test.txt", "confidence": 0.9}} # 'content' is missing
            }
        }
        # Simulate max attempts reached
        self.cm.clarification_history[hash(original_text)] = self.cm.max_clarification_attempts 
        
        result = self.cm.manage_clarification(context)
        self.assertTrue(result["clarification_needed"])
        self.assertIn("手動で操作してください", result["response"]["text"])
        self.assertIn("不足情報: content", result["response"]["text"]) 
        self.assertEqual(self.cm.clarification_history[hash(original_text)], 0) # History reset

        # Reset context for the next call to avoid early return
        context["clarification_needed"] = False
        # Simulate max attempts reached
        self.cm.clarification_history[hash(original_text)] = self.cm.max_clarification_attempts 
        
        result = self.cm.manage_clarification(context)
        self.assertTrue(result["clarification_needed"])
        self.assertIn("手動で操作してください", result["response"]["text"])
        self.assertIn("不足情報: content", result["response"]["text"])
        self.assertEqual(self.cm.clarification_history[hash(original_text)], 0) # History reset

    def test_no_clarification_needed(self):
        context = {
            "original_text": "明確な指示",
            "analysis": {"intent": "FILE_CREATE", "intent_confidence": 0.95,
                         "entities": {"filename": {"value": "test.txt", "confidence": 0.95},
                                      "content": {"value": "hello", "confidence": 0.95}}
            },
        }
        result = self.cm.manage_clarification(context)
        self.assertFalse(result["clarification_needed"])
        self.assertIsNone(result.get("response", {}).get("text")) # No response text generated for clarification
        self.assertEqual(self.cm.clarification_history[hash(context["original_text"])], 0)

if __name__ == '__main__':
    unittest.main()
