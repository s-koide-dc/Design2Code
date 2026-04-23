import unittest
import os
import shutil
import time
import json
from src.pipeline_core.pipeline_core import Pipeline
import sys
from unittest.mock import patch
import errno

# Assume required resources for Planner and TaskManager are set up (e.g., task_definitions.json, retry_rules.json)
# For integration tests, we need to ensure these files exist or are mocked properly.
# For simplicity, we'll create dummy JSON files for task_definitions and retry_rules here.

class TestPipelineIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize pipeline once for all tests to save time on model loading."""
        # Create dummy resource files for new modules
        cls.test_resources_dir = "integration_test_resources"
        os.makedirs(cls.test_resources_dir, exist_ok=True)
        
        # task_definitions.json
        cls.task_definitions_path = os.path.join(cls.test_resources_dir, "task_definitions.json")
        with open(cls.task_definitions_path, "w", encoding="utf-8") as f:
            json.dump({
                "FILE_CREATE": {
                    "states": ["INIT", "AWAITING_FILENAME", "AWAITING_CONTENT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["filename", "content"],
                    "transitions": {
                        "INIT": [
                            {
                                "condition": {
                                    "type": "all_of",
                                    "predicates": [
                                        {"type": "entity_exists", "key": "filename"},
                                        {"type": "entity_exists", "key": "content"}
                                    ]
                                },
                                "next_state": "READY_FOR_EXECUTION"
                            },
                            {
                                "condition": {"type": "entity_exists", "key": "filename"},
                                "next_state": "AWAITING_CONTENT"
                            }
                        ],
                        "AWAITING_CONTENT": [
                            {
                                "condition": {"type": "entity_exists", "key": "content"},
                                "next_state": "READY_FOR_EXECUTION"
                            }
                        ]
                    },
                    "clarification_messages": {
                        "filename": "ファイル名を教えていただけますか？",
                        "content": "ファイルの内容を教えていただけますか？"
                    }
                },
                "FILE_APPEND": {
                    "states": ["INIT", "AWAITING_FILENAME", "AWAITING_CONTENT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["filename", "content"],
                    "transitions": {
                        "INIT": [
                            {
                                "condition": {
                                    "type": "all_of",
                                    "predicates": [
                                        {"type": "entity_exists", "key": "filename"},
                                        {"type": "entity_exists", "key": "content"}
                                    ]
                                },
                                "next_state": "READY_FOR_EXECUTION"
                            },
                            {
                                "condition": {"type": "entity_exists", "key": "filename"},
                                "next_state": "AWAITING_CONTENT"
                            }
                        ],
                        "AWAITING_CONTENT": [
                            {
                                "condition": {"type": "entity_exists", "key": "content"},
                                "next_state": "READY_FOR_EXECUTION"
                            }
                        ]
                    },
                    "clarification_messages": {
                        "filename": "追記するファイル名を教えていただけますか？",
                        "content": "追記する内容を教えていただけますか？"
                    }
                },
                "FILE_DELETE": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["filename"],
                    "transitions": {
                        "INIT": [
                            {"condition": {"type": "entity_exists", "key": "filename"}, "next_state": "READY_FOR_EXECUTION"}
                        ]
                    },
                    "clarification_messages": {
                        "filename": "削除するファイル名を教えていただけますか？"
                    }
                },
                "FILE_READ": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["filename"],
                    "transitions": {
                        "INIT": [
                            {"condition": {"type": "entity_exists", "key": "filename"}, "next_state": "READY_FOR_EXECUTION"}
                        ]
                    },
                    "clarification_messages": {
                        "filename": "読み込むファイル名を教えていただけますか？"
                    }
                },
                "LIST_DIR": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": [],
                    "transitions": {
                        "INIT": [
                            {"condition": {"type": "always_true"}, "next_state": "READY_FOR_EXECUTION"}
                        ]
                    }
                },
                "CMD_RUN": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["command"],
                    "transitions": {
                        "INIT": [
                            {"condition": {"type": "entity_exists", "key": "command"}, "next_state": "READY_FOR_EXECUTION"}
                        ]
                    },
                    "clarification_messages": {
                        "command": "実行するコマンドを教えていただけますか？"
                    }
                },
                "GENERATE_TESTS": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["filename"],
                    "transitions": {
                        "INIT": [
                            {"condition": {"type": "entity_exists", "key": "filename"}, "next_state": "READY_FOR_EXECUTION"}
                        ]
                    },
                    "clarification_messages": {
                        "filename": "テストを生成するファイル名を教えていただけますか？"
                    }
                },
                "EXECUTE_GOAL_DRIVEN_TDD": {
                    "states": ["INIT", "AWAITING_CRITERIA", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["goal_description", "acceptance_criteria"],
                    "transitions": {
                        "INIT": [
                            {
                                "condition": {
                                    "type": "all_of",
                                    "predicates": [
                                        {"type": "entity_exists", "key": "goal_description"},
                                        {"type": "entity_exists", "key": "acceptance_criteria"}
                                    ]
                                },
                                "next_state": "READY_FOR_EXECUTION"
                            },
                            {
                                "condition": {"type": "entity_exists", "key": "goal_description"},
                                "next_state": "AWAITING_CRITERIA"
                            }
                        ],
                        "AWAITING_CRITERIA": [
                            {
                                "condition": {"type": "entity_exists", "key": "acceptance_criteria"},
                                "next_state": "READY_FOR_EXECUTION"
                            }
                        ]
                    },
                    "clarification_messages": {
                        "goal_description": "実装したい機能の目標を教えていただけますか？",
                        "acceptance_criteria": "受け入れ条件を教えていただけますか？（複数可）"
                    }
                },
                "REVERSE_DICTIONARY_SEARCH": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["query"],
                    "transitions": {
                        "INIT": [
                            {"condition": {"type": "entity_exists", "key": "query"}, "next_state": "READY_FOR_EXECUTION"}
                        ]
                    },
                    "clarification_messages": {
                        "query": "どのような意味の言葉を探しますか？"
                    }
                },
                "DOC_GEN": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["target_file"],
                    "transitions": {
                        "INIT": [
                            {"condition": {"type": "entity_exists", "key": "target_file"}, "next_state": "READY_FOR_EXECUTION"}
                        ]
                    },
                    "clarification_messages": {
                        "target_file": "設計書を生成する対象のソースファイル名を教えていただけますか？"
                    }
                },
                "DOC_REFINE": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["filename"],
                    "transitions": {
                        "INIT": [
                            {"condition": {"type": "entity_exists", "key": "filename"}, "next_state": "READY_FOR_EXECUTION"}
                        ]
                    },
                    "clarification_messages": {
                        "filename": "補完する対象の設計書ファイル名（.design.md）を教えていただけますか？"
                    }
                }
            }, f, ensure_ascii=False, indent=2)

        # retry_rules.json
        cls.retry_rules_path = os.path.join(cls.test_resources_dir, "retry_rules.json")
        with open(cls.retry_rules_path, "w", encoding="utf-8") as f:
            json.dump({
                "retry_rules": [
                    {
                        "error_type": "FileNotFoundError",
                        "condition": "filename is similar to existing files",
                        "suggestion": "指定されたファイルが見つかりませんでした。もしかして '{suggested_filename}' のことでしょうか？",
                        "alternative_action": "LIST_DIR",
                        "alternative_message": "ファイル一覧を表示しますか？"
                    },
                    {
                        "error_type": "PermissionError",
                        "condition": "action is FILE_CREATE or FILE_APPEND",
                        "suggestion": "権限エラーが発生しました。別の場所（例: ワークスペースのルート）に作成してみますか？",
                        "alternative_action": "PROMPT_FOR_NEW_LOCATION",
                        "alternative_message": "別のパスを指定してください。"
                    }
                ]
            }, f, ensure_ascii=False, indent=2)

        # Suppress initial model loading print statements for cleaner test output
        original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        try:
            # Re-initialize Pipeline with mocked paths for new resource files
            # Note: This might require modifying Pipeline.__init__ or mocking os.path.join
            # For simplicity, we assume Pipeline defaults to 'resources/' and will move our dummies there
            # or dynamically adjust sys.path.
            # A better approach would be to pass these paths to Pipeline.__init__
            cls.pipeline = Pipeline(
                clarification_thresholds={"intent": 0.75, "entity": 0.75}, # Set a lower threshold for testing
                planner_intent_threshold=0.8 # Set a lower threshold for Planner as well
            )
            
            # Manually set paths for relevant managers to our dummy files
            cls.pipeline.task_manager.task_definitions_path = cls.task_definitions_path
            # Need to reload task_definitions after path change
            cls.pipeline.task_manager.task_definitions = cls.pipeline.task_manager._load_task_definitions(cls.task_definitions_path)

            cls.pipeline.planner.retry_rules_path = cls.retry_rules_path
            cls.pipeline.planner.retry_rules = cls.pipeline.planner._load_retry_rules(cls.retry_rules_path)



        finally:
            sys.stdout.close()
            sys.stdout = original_stdout

        cls.test_ws = os.path.abspath("integration_test_workspace")
        if os.path.exists(cls.test_ws):
            shutil.rmtree(cls.test_ws)
        os.makedirs(cls.test_ws)
        # Point action executor to the isolated test workspace
        cls.pipeline.action_executor.workspace_root = cls.test_ws

    @classmethod
    def tearDownClass(cls):
        """Clean up the test workspace and dummy resource files."""
        if os.path.exists(cls.test_ws):
            shutil.rmtree(cls.test_ws)
        if os.path.exists(cls.test_resources_dir):
            shutil.rmtree(cls.test_resources_dir)

    def setUp(self):
        """Clear conversation history before each test case for isolation."""
        self.pipeline.context_manager.history = {}
        # Clear task manager history for isolation
        self.pipeline.task_manager.active_tasks = {}
        # Clean up any files created during a test
        for item in os.listdir(self.test_ws):
            item_path = os.path.join(self.test_ws, item)
            if os.path.isfile(item_path):
                os.remove(item_path)

    def test_greeting_and_smalltalk(self):
        """Tests basic conversational abilities like greetings and small talk."""
        test_cases = {
            "Greeting": {
                "input": "こんにちは",
                "expected_intent": "GREETING",
            },
            "Smalltalk": {
                "input": "元気？",
                "expected_intent": "PERSONAL_Q",
            },
            "Emotional": {
                "input": "疲れたな",
                "expected_intent": "EMOTIVE",
            }
        }
        for name, case in test_cases.items():
            with self.subTest(name):
                result = self.pipeline.run(case["input"])
                self.assertEqual(result["analysis"]["intent"], case["expected_intent"])
                self.assertGreaterEqual(result["analysis"]["intent_confidence"], 0.7) # Check confidence
                self.assertFalse(result.get("clarification_needed", False)) # Should not need clarification
                self.assertGreater(len(result.get("response", {}).get("text", "")), 0)

    def test_definition_query(self):
        """Tests the ability to answer 'What is X?' questions for a word in the dictionary."""
        result = self.pipeline.run("エージェントとは何？")
        self.assertEqual(result["analysis"]["intent"], "DEFINITION")
        self.assertIn("ユーザーの代わりに特定のタスクやアクションを実行するソフトウェア。", result.get("response", {}).get("text", ""))
        self.assertFalse(result.get("clarification_needed", False))

    def test_definition_query_class(self):
        """Tests the user-reported issue with 'クラス'."""
        result = self.pipeline.run("クラスとは")
        self.assertEqual(result["analysis"]["intent"], "DEFINITION")
        self.assertIn("class", result.get("response", {}).get("text", "")) # Check for the English meaning
        self.assertFalse(result.get("clarification_needed", False))

    def test_definition_query_not_found(self):
        """Tests a query for a word that is definitely not in the dictionary."""
        result = self.pipeline.run("量子コンピュータネットワークとは何ですか？")
        self.assertEqual(result["analysis"]["intent"], "DEFINITION")
        self.assertIn("申し訳ありません。「量子コンピュータネットワーク」の意味は辞書に見つかりませんでした。", result.get("response", {}).get("text", ""))
        self.assertFalse(result.get("clarification_needed", False))

    def test_file_creation_and_listing(self):
        """Tests creating a file and then listing it."""
        # 1. Create a file
        res1 = self.pipeline.run("test.txt を作って。内容は「first file」で。")
        self.assertFalse(res1.get("clarification_needed", False))
        self.assertIn("plan", res1) # Plan should be created
        self.assertEqual(res1["plan"]["action_method"], "_create_file")
        self.assertEqual(res1["plan"]["parameters"]["filename"], "test.txt")
        
        # Simulate user approval (if confirmation_needed is True) - For now, we assume direct execution post-plan
        self.assertEqual(res1["action_result"]["status"], "success")
        self.assertTrue(os.path.exists(os.path.join(self.test_ws, "test.txt")))
        self.assertIn("ファイル 'test.txt' を作成しました。", res1.get("response", {}).get("text", ""))


        # 2. List the directory to see the new file
        res2 = self.pipeline.run("ファイル一覧を")
        self.assertFalse(res2.get("clarification_needed", False))
        self.assertEqual(res2["analysis"]["intent"], "LIST_DIR")
        self.assertEqual(res2["action_result"]["status"], "success")
        self.assertIn("test.txt", res2["action_result"]["message"])
        self.assertIn("ディレクトリ", res2.get("response", {}).get("text", ""))


    def test_contextual_file_read(self):
        """Tests reading a file using anaphora (e.g., 'it')."""
        # First, create a file to establish context
        self.pipeline.run("context.log というファイルを作成して。中身は『Context Test』にして。")

        # Now, try to read 'it'
        result = self.pipeline.run("それを読み込んで")
        self.assertFalse(result.get("clarification_needed", False))
        # Check if anaphora was resolved correctly
        self.assertEqual(result["analysis"]["entities"]["filename"]["value"], "context.log")
        self.assertEqual(result["action_result"]["status"], "success")
        self.assertIn("Context Test", result["action_result"]["message"])

    def test_safe_command_execution(self):
        """Tests execution of whitelisted, safe commands, expecting confirmation."""
        # 'ls' or 'dir' is a safe, whitelisted command.
        command = "ls -l" if sys.platform != "win32" else "dir"
        
        result = self.pipeline.run(f"「{command}」を実行")
        
        self.assertIn("plan", result)
        self.assertEqual(result["plan"]["action_method"], "_run_command")
        self.assertEqual(result["plan"]["parameters"]["command"], command)
        self.assertTrue(result["plan"]["confirmation_needed"]) # CMD_RUN needs confirmation
        
        # With the new soft block logic, this should now request confirmation and clarify
        self.assertTrue(result.get("clarification_needed", False))
        self.assertIn("response", result)
        self.assertIn("text", result["response"])
        self.assertIn(f"コマンド '{command}' を実行します。よろしいですか？", result["response"]["text"])
        self.assertIn("soft_block_confirmation", result["pipeline_history"])
        self.assertNotIn("action_result", result) # Action should not have been executed yet


    def test_unauthorized_command_rejection(self):
        """Tests that a non-whitelisted command is rejected and confirmation is requested."""
        result = self.pipeline.run("「rm -rf /」を実行して")
        self.assertFalse(result.get("clarification_needed", False))
        self.assertIn("response", result)
        self.assertIn("text", result["response"])
        self.assertIn("Safety Policy Error", result["response"]["text"])
        self.assertNotIn("action_result", result)

    def test_path_traversal_rejection(self):
        """Tests that attempts to access files outside the workspace are blocked."""
        result = self.pipeline.run("ファイル ../secret.txt を読んで")
        self.assertFalse(result.get("clarification_needed", False))
        self.assertIn("plan", result)
        self.assertEqual(result["plan"]["action_method"], "_read_file")
        self.assertEqual(result["plan"]["parameters"]["filename"], "../secret.txt")

        # Assuming direct execution, ActionExecutor should block it
        self.assertEqual(result["analysis"]["intent"], "FILE_READ")
        self.assertEqual(result["action_result"]["status"], "error")
        # Check against error patterns
        self.assertIn("無効なパスです。", result.get("action_result", {}).get("message", "")) # Updated expected message

    def test_file_creation_with_specified_name(self):
        """Tests creating a file with a name specified using '名前は' phrase."""
        input_text = "新しいファイルを作成してください、名前はmy_file.txt、内容は「テストコンテンツ」です。"
        expected_filename = "my_file.txt"
        expected_content = "テストコンテンツ"

        res = self.pipeline.run(input_text)
        self.assertFalse(res.get("clarification_needed", False))
        self.assertIn("plan", res)
        self.assertEqual(res["plan"]["action_method"], "_create_file")
        self.assertEqual(res["plan"]["parameters"]["filename"], expected_filename)
        self.assertEqual(res["plan"]["parameters"]["content"], expected_content)
        
        self.assertEqual(res["action_result"]["status"], "success")
        self.assertTrue(os.path.exists(os.path.join(self.test_ws, expected_filename)))
        with open(os.path.join(self.test_ws, expected_filename), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), expected_content)
        self.assertIn(f"ファイル '{expected_filename}' を作成しました。", res.get("response", {}).get("text", ""))

    def test_file_append(self):
        """Tests appending content to an existing file."""
        filename = "append_test.txt"
        initial_content = "Initial line."
        append_content = "Appended line."

        # Create initial file
        self.pipeline.run(f"ファイル {filename} を作成して。中身は『{initial_content}』にして。")

        # Append content
        res = self.pipeline.run(f"ファイル {filename} に『{append_content}』を追記してほしい。")
        self.assertTrue(res.get("clarification_needed", False)) # Should ask for confirmation
        self.assertIn("plan", res)
        self.assertEqual(res["plan"]["action_method"], "_append_file")
        self.assertEqual(res["plan"]["parameters"]["filename"], filename)
        self.assertEqual(res["plan"]["parameters"]["content"], append_content)
        # Assuming confirmation message includes action description
        self.assertIn(f"ファイル '{filename}' に追記します。よろしいですか？", res["response"]["text"])
        
        # This test currently does not simulate user approval, so action_result won't be success
        # For now, we only check that confirmation is requested.
        # self.assertEqual(res["action_result"]["status"], "success")
        # with open(os.path.join(self.test_ws, filename), "r", encoding="utf-8") as f:
        #     self.assertEqual(f.read(), f"{initial_content}\n{append_content}")
        # self.assertIn(f"ファイル '{filename}' に追記しました。", res.get("response", {}).get("text", ""))

    def test_file_delete(self):
        """Tests deleting an existing file."""
        filename = "delete_test.txt"
        # Create file to be deleted
        self.pipeline.run(f"ファイル {filename} を作成して。中身は『Temporary content』にして。")
        self.assertTrue(os.path.exists(os.path.join(self.test_ws, filename)))

        # Delete file
        res = self.pipeline.run(f"ファイル {filename} を削除してほしい。")
        self.assertTrue(res.get("clarification_needed", False)) # Should ask for confirmation
        self.assertIn("plan", res)
        self.assertEqual(res["plan"]["action_method"], "_delete_file")
        self.assertEqual(res["plan"]["parameters"]["filename"], filename)
        # Assuming confirmation message includes action description
        self.assertIn(f"ファイル '{filename}' を削除します。よろしいですか？", res["response"]["text"])

        # This test currently does not simulate user approval, so action_result won't be success
        # For now, we only check that confirmation is requested.
        # self.assertEqual(res["action_result"]["status"], "success")
        # self.assertFalse(os.path.exists(os.path.join(self.test_ws, filename)))
        # self.assertIn(f"ファイル '{filename}' を削除しました。", res.get("response", {}).get("text", ""))

    def test_list_dir_task(self):
        """Tests listing directory content as a task."""
        res1 = self.pipeline.run("dummy.txt を作って。内容は『dummy』にして。")
        self.assertFalse(res1.get("clarification_needed", False)) # Should not need clarification for file creation

        res = self.pipeline.run("ディレクトリの一覧を表示してほしい。")
        print(f"--- Test List Dir Task Debug --- Final Response Context: {res}")
        self.assertFalse(res.get("clarification_needed", False)) # LIST_DIR does not need confirmation
        self.assertIn("plan", res)
        self.assertEqual(res["plan"]["action_method"], "_list_dir")
        self.assertIn("dummy.txt", res["action_result"]["message"])
        self.assertEqual(res["action_result"]["status"], "success")

    def test_cmd_run_task(self):
        """Tests running a safe command as a task, expecting confirmation."""
        command = "echo Hello" if sys.platform != "win32" else "echo Hello" # Example safe command
        
        # Command execution should require confirmation
        res = self.pipeline.run(f"コマンド「{command}」を実行して。")
        self.assertTrue(res.get("clarification_needed", False)) # Should ask for confirmation
        self.assertIn("plan", res)
        self.assertEqual(res["plan"]["action_method"], "_run_command")
        self.assertEqual(res["plan"]["parameters"]["command"], command)
        self.assertTrue(res["plan"]["confirmation_needed"])
        self.assertIn(f"コマンド '{command}' を実行します。よろしいですか？", res["response"]["text"])

        # Simulate approval and run (This part is not fully implemented in ActionExecutor yet,
        # but for now, we expect plan to be created and confirmation asked.)
        # If ActionExecutor was to automatically proceed, we'd check its status.
        # For current test, we check that plan is correctly generated.

    def test_file_read_task(self):
        """Tests reading a file as a task."""
        filename = "read_task.txt"
        content = "Content to be read."
        self.pipeline.run(f"ファイル {filename} を作成して。中身は『{content}』にして。")

        res = self.pipeline.run(f"ファイル {filename} を読んでほしい。")
        self.assertFalse(res.get("clarification_needed", False)) 
        self.assertIn("plan", res)
        self.assertEqual(res["plan"]["action_method"], "_read_file")
        self.assertEqual(res["plan"]["parameters"]["filename"], filename)
        self.assertEqual(res["action_result"]["status"], "success")
        self.assertIn(content, res["action_result"]["message"])

    # --- New Test Cases for ClarificationManager, Planner, TaskManager ---
    def test_clarification_low_intent_confidence(self):
        # Default intent_threshold is 0.75. Input "曖昧な指示" gives intent "GENERAL" with confidence 0.5.
        # Since 0.5 < 0.75, clarification should be needed.
        result = self.pipeline.run("曖昧な指示") 
        self.assertTrue(result.get("clarification_needed", False))
        self.assertIn("意図が明確ではありません。", result.get("response", {}).get("text", ""))
        self.assertIn("GENERAL", result.get("response", {}).get("text", "")) # Assuming "GENERAL" intent for ambiguous input
        self.assertIn("clarification_manager", result["pipeline_history"])

    def test_clarification_missing_entity(self):
        # FILE_CREATE requires 'filename' and 'content'. Providing only filename.
        result = self.pipeline.run("test_missing.txt を作って") 
        self.assertTrue(result.get("clarification_needed", False))
        self.assertIn("ファイルの内容を教えていただけますか？", result.get("response", {}).get("text", ""))
        self.assertIn("clarification_manager", result["pipeline_history"])
        self.assertEqual(result["analysis"]["intent"], "FILE_CREATE")

    def test_planner_plan_not_created_due_to_low_confidence(self):
        # Lower intent confidence to prevent plan creation (should be caught by Planner)
        original_intent_threshold = self.pipeline.planner.intent_threshold
        self.pipeline.planner.intent_threshold = 0.99
        
        try:
            # Input with high intent_confidence but Planner's threshold is higher
            result = self.pipeline.run("明確な指示")
            self.assertTrue(result.get("clarification_needed", False)) # Clarification should be needed
            self.assertIn("response", result)
            # Accept either the generic fallback OR the specific clarification for the most likely (but low confidence) intent
            response_text = result.get("response", {}).get("text", "")
            self.assertTrue("意図が明確ではありません" in response_text or "教えていただけますか" in response_text)
            self.assertIsNone(result.get("plan")) # Plan should not be created (or be None)
            self.assertIn("clarification_manager", result["pipeline_history"])
        finally:
            self.pipeline.planner.intent_threshold = original_intent_threshold

    def test_task_manager_state_transition(self):
        session_id = "test_task_manager_session"
        
        original_clarification_intent_threshold = self.pipeline.clarification_manager.intent_threshold
        original_planner_intent_threshold = self.pipeline.planner.intent_threshold

        # Set low to bypass clarification and planning for 0.5 confidence
        self.pipeline.clarification_manager.intent_threshold = 0.4
        self.pipeline.planner.intent_threshold = 0.4 

        try:
            # 1. Start FILE_CREATE task, filename provided
            result1 = self.pipeline.run(f"session_id:{session_id} new_file_from_tm.txt を作って")
            self.assertIn("task", result1)
            self.assertEqual(result1["task"]["name"], "FILE_CREATE")
            self.assertEqual(result1["task"]["state"], "AWAITING_CONTENT")
            self.assertTrue(result1["clarification_needed"])
            self.assertIn("ファイルの内容を教えていただけますか？", result1.get("response", {}).get("text", ""))

            # 2. Continue FILE_CREATE task, content provided
            result2 = self.pipeline.run(f"session_id:{session_id} 内容は「TM Test Content」で")
            self.assertIn("task", result2)
            self.assertEqual(result2["task"]["name"], "FILE_CREATE")
            self.assertEqual(result2["task"]["state"], "COMPLETED") # This is the failing assertion
            self.assertFalse(result2.get("clarification_needed", False))
            self.assertEqual(result2["action_result"]["status"], "success")
            self.assertTrue(os.path.exists(os.path.join(self.test_ws, "new_file_from_tm.txt")))
            with open(os.path.join(self.test_ws, "new_file_from_tm.txt"), "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), "TM Test Content")

        finally:
            # Clean up the task and restore thresholds after assertions
            self.pipeline.task_manager.reset_task(session_id)
            self.pipeline.clarification_manager.intent_threshold = original_clarification_intent_threshold # Restore original threshold
            self.pipeline.planner.intent_threshold = original_planner_intent_threshold # Restore original threshold


    def test_task_manager_isolated_state_change(self):
        session_id = "isolated_session"
        initial_context = {
            "session_id": session_id,
            "original_text": f"session_id:{session_id} test.txt を作って。内容は「Isolation Test」で。",
            "analysis": {
                "intent": "FILE_CREATE",
                "entities": {
                    "filename": {"value": "test.txt", "confidence": 1.0},
                    "content": {"value": "Isolation Test", "confidence": 1.0}
                }
            }
        }

        # Simulate manage_task_state which should set state to READY_FOR_EXECUTION
        context_after_manage = self.pipeline.task_manager.manage_task_state(initial_context)
        self.assertIn("task", context_after_manage)
        self.assertEqual(context_after_manage["task"]["state"], "READY_FOR_EXECUTION")
        self.assertIn(session_id, self.pipeline.task_manager.active_tasks)
        self.assertEqual(self.pipeline.task_manager.active_tasks[session_id]["state"], "READY_FOR_EXECUTION")

        # Simulate action execution success
        context_after_manage["action_result"] = {"status": "success", "message": "File created."}

        # Simulate update_task_after_execution
        final_context = self.pipeline.task_manager.update_task_after_execution(context_after_manage)

        # Assert the final state in the returned context and in active_tasks
        self.assertEqual(final_context["task"]["state"], "COMPLETED")
        self.assertNotIn(session_id, self.pipeline.task_manager.active_tasks) 
        self.assertEqual(self.pipeline.task_manager.active_tasks.get(session_id), None) # Should be None after reset
        
        # Clean up
        self.pipeline.task_manager.reset_task(session_id)

    def test_session_isolation(self):
        """Tests that two sessions can run tasks concurrently without interference."""
        session_A = "session_A"
        session_B = "session_B"

        # 1. Start task in session_A
        res_A1 = self.pipeline.run(f"session_id:{session_A} ファイルを作成して")
        self.assertTrue(res_A1.get("clarification_needed"))
        self.assertIn("ファイル名を教えていただけますか？", res_A1["response"]["text"])
        self.assertEqual(self.pipeline.task_manager.active_tasks[session_A]["state"], "INIT")

        # 2. Start task in session_B
        res_B1 = self.pipeline.run(f"session_id:{session_B} 新しいファイルを作りたい")
        self.assertTrue(res_B1.get("clarification_needed"))
        self.assertIn("ファイル名を教えていただけますか？", res_B1["response"]["text"])
        self.assertEqual(self.pipeline.task_manager.active_tasks[session_B]["state"], "INIT")

        # 3. Provide filename to session_A
        res_A2 = self.pipeline.run(f"session_id:{session_A} file_A.txt")
        self.assertTrue(res_A2.get("clarification_needed"))
        self.assertIn("ファイルの内容を教えていただけますか？", res_A2["response"]["text"])
        self.assertEqual(self.pipeline.task_manager.active_tasks[session_A]["state"], "AWAITING_CONTENT")

        # 4. Assert that session_B's task is NOT affected
        self.assertEqual(self.pipeline.task_manager.active_tasks[session_B]["state"], "INIT", "Session B state should not change")
        self.assertEqual(self.pipeline.task_manager.active_tasks[session_B]["parameters"], {}, "Session B parameters should be empty")

        # 5. Provide filename to session_B
        res_B2 = self.pipeline.run(f"session_id:{session_B} file_B.txt")
        self.assertTrue(res_B2.get("clarification_needed"))
        self.assertIn("ファイルの内容を教えていただけますか？", res_B2["response"]["text"])
        self.assertEqual(self.pipeline.task_manager.active_tasks[session_B]["state"], "AWAITING_CONTENT")
        
        # 6. Assert that session_A's task is NOT affected
        self.assertEqual(self.pipeline.task_manager.active_tasks[session_A]["state"], "AWAITING_CONTENT", "Session A state should not change")

        # 7. Complete task in session_A
        res_A3 = self.pipeline.run(f"session_id:{session_A} 内容は「Session A Content」です")
        self.assertFalse(res_A3.get("clarification_needed", False))
        self.assertEqual(res_A3["action_result"]["status"], "success")
        self.assertTrue(os.path.exists(os.path.join(self.test_ws, "file_A.txt")))
        with open(os.path.join(self.test_ws, "file_A.txt"), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Session A Content")

        # 8. Complete task in session_B
        res_B3 = self.pipeline.run(f"session_id:{session_B} 中身は『Session B Content』で")
        self.assertFalse(res_B3.get("clarification_needed", False))
        self.assertEqual(res_B3["action_result"]["status"], "success")
        self.assertTrue(os.path.exists(os.path.join(self.test_ws, "file_B.txt")))
        with open(os.path.join(self.test_ws, "file_B.txt"), "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "Session B Content")

    @patch('src.file_operations.file_operations.open')
    def test_robustness_storage_full(self, mock_open):
        """Tests pipeline's response to a storage full error during file creation."""
        mock_open.side_effect = OSError(errno.ENOSPC, "No space left on device")
        
        result = self.pipeline.run("ファイル 'no_space.txt' を作って。内容は「test」で。")
        
        self.assertEqual(result['action_result']['status'], 'error')
        self.assertIn("ディスク容量が不足しています", result['action_result']['message'])

    @patch('src.file_operations.file_operations.open')
    def test_robustness_permission_denied(self, mock_open):
        """Tests pipeline's response to a permission error during file creation."""
        mock_open.side_effect = PermissionError("Permission denied")
        
        result = self.pipeline.run("ファイル 'permission.txt' を作って。内容は「test」で。")
        
        self.assertEqual(result['action_result']['status'], 'error')
        self.assertIn("操作に必要な権限がありません", result['action_result']['message'])

    def test_robustness_long_input(self):
        """Tests if the pipeline can handle very long content without crashing."""
        long_content = "a" * (1024 * 1) # 1KB string (Reduced from 100KB to keep logs manageable)
        filename = "long_content.txt"
        
        # This test primarily checks for crashes and basic success.
        # A more advanced test might check for performance.
        try:
            result = self.pipeline.run(f"ファイル '{filename}' を作成して。内容は『{long_content}』")
            
            self.assertEqual(result['action_result']['status'], 'success')
            self.assertTrue(os.path.exists(os.path.join(self.test_ws, filename)))
            with open(os.path.join(self.test_ws, filename), "r", encoding="utf-8") as f:
                # We don't need to check the whole content, just that it's not empty and seems right
                self.assertEqual(len(f.read()), len(long_content))
        except Exception as e:
            self.fail(f"Pipeline crashed with very long input: {e}")

if __name__ == "__main__":
    unittest.main(verbosity=2)
