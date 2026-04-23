import unittest
from src.response_generator.response_generator import ResponseGenerator

class TestResponseGenerator(unittest.TestCase):

    def setUp(self):
        self.generator = ResponseGenerator()

    def test_happy_path_weather_question_with_concept(self):
        """
        ハッピーパス: 「天気」と関連概念「晴れ」がトピックにある場合、テンプレート応答を生成する。
        """
        initial_context = {
            "analysis": {"topics": ["今日", "天気", "晴れ"]},
            "pipeline_history": ["morph_analyzer", "syntactic_analyzer", "semantic_analyzer"]
        }
        
        result_context = self.generator.generate(initial_context)
        
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertGreater(len(result_context["response"]["text"]), 0) # Check if response text is not empty
        self.assertIn("response_generator", result_context["pipeline_history"])
        self.assertEqual(len(result_context.get("errors", [])), 0)

    def test_unknown_concept(self):
        """
        主要トピックは存在するが、関連概念が見つからない場合、トピックに特化したデフォルト応答を返す。
        """
        initial_context = {"analysis": {"topics": ["今日", "天気"]}, "pipeline_history": []}
        
        result_context = self.generator.generate(initial_context)
        
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertGreater(len(result_context["response"]["text"]), 0) # Check if response text is not empty

    def test_no_known_topic(self):
        """
        既知のトピックが一つもない場合、汎用のデフォルト応答を返す。
        """
        initial_context = {"analysis": {"topics": ["猫", "かわいい"]}, "pipeline_history": []}
        
        result_context = self.generator.generate(initial_context)
        
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertGreater(len(result_context["response"]["text"]), 0) # Check if response text is not empty

    def test_edge_case_empty_topics(self):
        """
        エッジケース: 空のトピックリスト。
        """
        initial_context = {"analysis": {"topics": []}, "pipeline_history": []}
        
        result_context = self.generator.generate(initial_context)
        
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertGreater(len(result_context["response"]["text"]), 0) # Check if response text is not empty
        self.assertIn("response_generator", result_context["pipeline_history"])

    def test_edge_case_no_topics(self):
        """
        エッジケース: contextにtopicsキーが存在しない場合、エラーではなくデフォルト応答を返す。
        """
        initial_context = {"analysis": {}, "pipeline_history": []}
        
        result_context = self.generator.generate(initial_context)
        
        self.assertEqual(len(result_context.get("errors", [])), 0) # No errors should be generated
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertEqual(result_context["response"]["text"], self.generator.default_response) # Should return default response


    def test_generate_confirmation_message_create_file(self):
        context = {
            "plan": {
                "action_method": "_create_file",
                "parameters": {"filename": "new_report.txt", "content": "test content"},
                "confirmation_needed": True
            },
            "pipeline_history": []
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertIn("ファイル 'new_report.txt' を作成します。よろしいですか？", result_context["response"]["text"])
        self.assertIn("response_generator_confirmation", result_context["pipeline_history"])

    def test_generate_confirmation_message_delete_file(self):
        context = {
            "plan": {
                "action_method": "_delete_file",
                "parameters": {"filename": "old_data.csv"},
                "confirmation_needed": True
            },
            "pipeline_history": []
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertIn("ファイル 'old_data.csv' を削除します。よろしいですか？", result_context["response"]["text"])
        self.assertIn("response_generator_confirmation", result_context["pipeline_history"])

    def test_generate_confirmation_message_run_command(self):
        context = {
            "plan": {
                "action_method": "_run_command",
                "parameters": {"command": "ls -la"},
                "confirmation_needed": True
            },
            "pipeline_history": []
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertIn("コマンド 'ls -la' を実行します。よろしいですか？", result_context["response"]["text"])
        self.assertIn("response_generator_confirmation", result_context["pipeline_history"])

    def test_generate_confirmation_message_unknown_action(self):
        context = {
            "plan": {
                "action_method": "_unknown_action",
                "parameters": {"item": "something"},
                "confirmation_needed": True
            },
            "pipeline_history": []
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertIn("不明な操作 (_unknown_action)します。よろしいですか？", result_context["response"]["text"])
        self.assertIn("response_generator_confirmation", result_context["pipeline_history"])

    def test_generate_compound_overall_approval_message(self):
        context = {
            "pipeline_history": [],
            "task": {
                "name": "BACKUP_AND_DELETE",
                "type": "COMPOUND_TASK",
                "parameters": {
                    "source_filename": {"value": "orig.txt"},
                    "destination_filename": {"value": "backup.txt"}
                },
                "subtasks": [
                    {"name": "FILE_COPY", "parameters": {"source_filename": {"value": "orig.txt"}}},
                    {"name": "FILE_DELETE", "parameters": {"filename": {"value": "orig.txt"}}}
                ],
                "clarification_message": "COMPOUND_TASK_OVERALL_APPROVAL"
            }
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertIn("ファイル 'orig.txt' を 'backup.txt' にバックアップして削除します。よろしいですか？", result_context["response"]["text"])

    def test_generate_compound_subtask_approval_message(self):
        context = {
            "pipeline_history": [],
            "task": {
                "name": "BACKUP_AND_DELETE",
                "type": "COMPOUND_TASK",
                "subtasks": [
                    {"name": "FILE_COPY", "parameters": {"source_filename": {"value": "orig.txt"}}},
                    {"name": "FILE_DELETE", "parameters": {"filename": {"value": "orig.txt"}}}
                ],
                "current_subtask_index": 1, # Index of FILE_DELETE
                "clarification_message": "COMPOUND_TASK_SUBTASK_APPROVAL"
            }
        }
        result_context = self.generator.generate_confirmation_message(context)
        self.assertIn("response", result_context)
        self.assertIn("text", result_context["response"])
        self.assertIn("複合タスク「BACKUP_AND_DELETE」の次のステップ：サブタスク「FILE_DELETE」を実行します。よろしいですか？", result_context["response"]["text"])

if __name__ == '__main__':
    unittest.main()