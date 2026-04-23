import unittest
import os
import shutil
import sys
import json
from src.pipeline_core.pipeline_core import Pipeline

class TestConversationScenarios(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialize pipeline once for all tests to save time on model loading."""
        
        # Create dummy resource files for new modules
        cls.test_resources_dir = os.path.abspath("conversation_test_resources")
        os.makedirs(cls.test_resources_dir, exist_ok=True)

        # --- NEW: Call update_intent_corpus here ---
        # Ensure intent corpus is updated before pipeline initialization
        
        def update_intent_corpus_for_tests():
            file_path = os.path.join(cls.test_resources_dir, "intent_corpus.json")
            
            test_intents_data = {
                "intents": [
                    {
                        "name": "PROVIDE_CONTENT",
                        "patterns": [
                            {"pattern": "^内容は", "confidence_score": 0.95},
                            {"pattern": "^中身は", "confidence_score": 0.95}
                        ],
                        "examples": ["本文は「こんにちは世界」です", "内容は「テスト」です", "内容は『こんにちは』です"]
                    },
                    {
                        "name": "GREETING",
                        "patterns": [ {"pattern": "^(?:こんにちは|おはよ[うう]|こんばん[はわ]|ハロー|うっす)[！!？?]*$", "confidence_score": 0.95} ],
                        "examples": ["おはよう", "ハロー", "こんにちは"]
                    },
                    {
                        "name": "BYE",
                        "patterns": [ {"pattern": "^(?:さようなら|バイバイ|またね|じゃあね)[！!？?]*$", "confidence_score": 0.95} ],
                        "examples": ["バイバイ", "またね"]
                    },
                    {
                        "name": "AGREE",
                        "patterns": [ {"pattern": "^(?:はい|お願いします|了解|りょ|OK|おk)$", "confidence_score": 0.9} ],
                        "examples": ["そうですね", "OK", "はい"]
                    },
                    {
                        "name": "DISAGREE",
                        "patterns": [ {"pattern": "^(?:いいえ|違います|ノー|ダメ|拒否)$", "confidence_score": 0.9} ],
                        "examples": ["違います", "ノー", "いいえ"]
                    },
                    {
                        "name": "TIME",
                        "patterns": [ {"pattern": "今何時？", "confidence_score": 0.9} ],
                        "examples": ["時間", "時計", "今何時？"]
                    },
                    {
                        "name": "FILE_CREATE",
                        "patterns": [
                            {"pattern": ".+を作(?:成|って|り|る|ら)", "confidence_score": 0.95},
                            {"pattern": "新規作成", "confidence_score": 0.95},
                            {"pattern": "新しいファイル", "confidence_score": 0.9}
                        ],
                        "examples": ["新規作成", "生成", "ファイルを作って"]
                    },
                    {
                        "name": "PERSONAL_Q",
                        "patterns": [
                            {"pattern": "元気？", "confidence_score": 0.9},
                            {"pattern": "調子はどう", "confidence_score": 0.9}
                        ],
                        "examples": ["元気ですか", "調子いい？"]
                    },
                    {
                        "name": "FILE_READ",
                        "patterns": [ 
                            {"pattern": "読(?:んで|む|み)", "confidence_score": 0.9},
                            {"pattern": "表示", "confidence_score": 0.9}
                        ],
                        "examples": ["内容を表示", "開いて", "読んで", "それを読んで"]
                    },
                    {
                        "name": "BACKUP_AND_DELETE",
                        "patterns": [ {"pattern": "バックアップ.*削除", "confidence_score": 0.98} ],
                        "examples": ["コピーして消す", "複製して削除", "バックアップして削除して"]
                    },
                    {
                        "name": "FILE_DELETE",
                        "patterns": [ {"pattern": "削除", "confidence_score": 0.95} ],
                        "examples": ["消して", "破棄"]
                    },
                    {
                        "name": "FILE_MOVE",
                        "patterns": [ {"pattern": "移動", "confidence_score": 0.9} ],
                        "examples": ["移して", "場所変更", "移動して"]
                    },
                    {
                        "name": "FILE_COPY",
                        "patterns": [ {"pattern": "コピー", "confidence_score": 0.9} ],
                        "examples": ["複製", "写し", "コピーして"]
                    },
                    {
                        "name": "GET_CWD",
                        "patterns": [ {"pattern": "今のパス", "confidence_score": 0.9} ],
                        "examples": ["現在地", "カレントディレクトリ", "今のパス"]
                    },
                    {
                        "name": "CMD_RUN",
                        "patterns": [
                            {"pattern": "コマンド「.+」を実行", "confidence_score": 0.99},
                            {"pattern": "コマンド.+を実行", "confidence_score": 0.99},
                            {"pattern": ".+コマンドを実行", "confidence_score": 0.98},
                            {"pattern": "実行", "confidence_score": 0.9}
                        ],
                        "examples": ["lsを実行して", "pwdコマンドを実行", "コマンドを実行して"]
                    }
                ]
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(test_intents_data, f, ensure_ascii=False, indent=4)

        update_intent_corpus_for_tests()
        # --- END NEW ---

        # Create dummy resource files for new modules (Copied from test_full_integrated_pipeline.py for isolation)
        cls.test_resources_dir = "conversation_test_resources"
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
                                        { "type": "entity_exists", "key": "filename" },
                                        { "type": "entity_exists", "key": "content" }
                                    ]
                                },
                                "next_state": "READY_FOR_EXECUTION"
                            },
                            {
                                "condition": { "type": "entity_exists", "key": "filename" },
                                "next_state": "AWAITING_CONTENT"
                            }
                        ],
                        "AWAITING_CONTENT": [
                                                    {
                                                        "condition": { "type": "entity_exists", "key": "content" },
                                                        "next_state": "READY_FOR_EXECUTION"
                                                    },
                                                    {
                                                        "condition": { "type": "intent_is", "intent": "PROVIDE_CONTENT" },
                                                        "next_state": "READY_FOR_EXECUTION"
                                                    }
                                                ]
                                            },
                                            "clarification_messages": {
                                                "filename": "ファイル名を教えていただけますか？",
                                                "content": "ファイルの内容を教えていただけますか？"
                                            }
                                        },
                                        "PROVIDE_CONTENT": {
                                            "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                                            "required_entities": ["content"],
                                            "transitions": {
                                                "INIT": [
                                                    { "condition": { "type": "entity_exists", "key": "content" }, "next_state": "READY_FOR_EXECUTION" }
                                                ]
                                            }
                                        },                "CMD_RUN": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["command"],
                    "transitions": {
                        "INIT": [
                            { "condition": { "type": "entity_exists", "key": "command" }, "next_state": "READY_FOR_EXECUTION" }
                        ]
                    },
                    "clarification_messages": {
                        "command": "実行するコマンドを教えていただけますか？"
                    }
                },
                "FILE_READ": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["filename"],
                    "transitions": {
                        "INIT": [
                            { "condition": { "type": "entity_exists", "key": "filename" }, "next_state": "READY_FOR_EXECUTION" }
                        ]
                    },
                    "clarification_messages": {
                        "filename": "読み込むファイル名を教えていただけますか？"
                    }
                },
                "FILE_MOVE": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["source_filename", "destination_filename"],
                    "transitions": {
                        "INIT": [
                            { "condition": { "type": "all_of", "predicates": [{ "type": "entity_exists", "key": "source_filename" }, { "type": "entity_exists", "key": "destination_filename" }] }, "next_state": "READY_FOR_EXECUTION" }
                        ]
                    },
                    "clarification_messages": {
                        "source_filename": "移動元のファイル名を教えていただけますか？",
                        "destination_filename": "移動先のファイル名を教えていただけますか？"
                    }
                },
                "FILE_COPY": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["source_filename", "destination_filename"],
                    "transitions": {
                        "INIT": [
                            { "condition": { "type": "all_of", "predicates": [{ "type": "entity_exists", "key": "source_filename" }, { "type": "entity_exists", "key": "destination_filename" }] }, "next_state": "READY_FOR_EXECUTION" }
                        ]
                    },
                    "clarification_messages": {
                        "source_filename": "コピー元のファイル名を教えていただけますか？",
                        "destination_filename": "コピー先のファイル名を教えていただけますか？"
                    }
                },
                "GET_CWD": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": [],
                    "transitions": {
                        "INIT": [
                            { "condition": { "type": "always_true" }, "next_state": "READY_FOR_EXECUTION" }
                        ]
                    }
                },
                "FILE_DELETE": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["filename"],
                    "transitions": {
                        "INIT": [
                            { "condition": { "type": "entity_exists", "key": "filename" }, "next_state": "READY_FOR_EXECUTION" }
                        ]
                    },
                    "clarification_messages": {
                        "filename": "削除するファイル名を教えていただけますか？"
                    }
                },
                "BACKUP_AND_DELETE": {
                    "type": "COMPOUND_TASK",
                    "subtasks": [
                        {
                            "name": "FILE_COPY",
                            "parameter_mapping": {
                                "source_filename": "source_filename",
                                "destination_filename": "destination_filename"
                            }
                        },
                        {
                            "name": "FILE_DELETE",
                            "parameter_mapping": {
                                "filename": "source_filename"
                            }
                        }
                    ],
                    "required_entities": ["source_filename", "destination_filename"],
                    "templates": {
                        "overall_approval": "ファイル '{source_filename}' を '{destination_filename}' にバックアップして削除します。よろしいですか？"
                    },
                    "clarification_messages": {
                        "source_filename": "バックアップし削除する元のファイル名を教えていただけますか？",
                        "destination_filename": "バックアップ先のファイル名を教えていただけますか？"
                    }
                },
                "CS_TEST_RUN": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["project_path"],
                    "transitions": {
                        "INIT": [
                            { "condition": { "type": "entity_exists", "key": "project_path" }, "next_state": "READY_FOR_EXECUTION" }
                        ]
                    },
                    "clarification_messages": {
                        "project_path": "テスト対象のプロジェクトパスを教えていただけますか？"
                    }
                },
                "CS_ANALYZE": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["filename"],
                    "transitions": {
                        "INIT": [
                            { "condition": { "type": "entity_exists", "key": "filename" }, "next_state": "READY_FOR_EXECUTION" }
                        ]
                    },
                    "clarification_messages": {
                        "filename": "解析対象のC#ファイル名を教えていただけますか？"
                    }
                },
                "CLARIFICATION_RESPONSE": {
                    "states": ["INIT", "AGREED", "DISAGREED", "COMPLETED"],
                    "required_entities": ["user_response"],
                    "transitions": {
                        "INIT": [
                            {
                                "condition": { "type": "entity_value_is", "key": "user_response", "value": "AGREE" },
                                "next_state": "AGREED"
                            },
                            {
                                "condition": { "type": "entity_value_is", "key": "user_response", "value": "DISAGREE" },
                                "next_state": "DISAGREED"
                            }
                        ]
                    }
                }
            }, f, ensure_ascii=False, indent=2)

        # retry_rules.json (Minimal for this test)
        cls.retry_rules_path = os.path.join(cls.test_resources_dir, "retry_rules.json")
        with open(cls.retry_rules_path, "w", encoding="utf-8") as f:
            json.dump({"retry_rules": []}, f, ensure_ascii=False, indent=2)

        # Suppress initial model loading print statements
        # original_stdout = sys.stdout
        # sys.stdout = open(os.devnull, 'w')
        try:
            # Initialize Pipeline
            # We use lower threshold for tests to ensure intent detection works with simple inputs
            cls.pipeline = Pipeline(
                clarification_thresholds={"intent": 0.6, "entity": 0.7}, 
                planner_intent_threshold=0.7
            )
            
            # Manually set paths for relevant managers to our dummy files
            cls.pipeline.task_manager.task_definitions_path = cls.task_definitions_path
            cls.pipeline.task_manager.task_definitions = cls.pipeline.task_manager._load_task_definitions(cls.task_definitions_path)

            # Lazy load intent_detector and set its corpus path
            _ = cls.pipeline.intent_detector
            cls.pipeline.intent_detector.corpus_path = os.path.join(cls.test_resources_dir, "intent_corpus.json")
            cls.pipeline.intent_detector.load_corpus()
            cls.pipeline.intent_detector.prepare_corpus_vectors(cls.pipeline.morph_analyzer)

            cls.pipeline.planner.retry_rules_path = cls.retry_rules_path
            cls.pipeline.planner.retry_rules = cls.pipeline.planner._load_retry_rules(cls.retry_rules_path)

        finally:
            # sys.stdout.close()
            # sys.stdout = original_stdout
            sys.stdout = sys.__stdout__ # Restore standard output

        cls.test_ws = os.path.abspath("conversation_test_workspace")
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
        # Clear task manager history
        self.pipeline.task_manager.active_tasks = {}
        # Clear any pending confirmation plans
        self.pipeline.context_manager.clear_pending_confirmation_plan()
        
        # Clean up any files created during a test
        for item in os.listdir(self.test_ws):
            item_path = os.path.join(self.test_ws, item)
            if os.path.isfile(item_path):
                os.remove(item_path)

    def run_conversation(self, flow):
        """
        Executes a conversation flow.
        flow: list of dicts, each containing:
            - 'user': str (User input)
            - 'expected_ai': str (Expected part of AI response) or None
            - 'confirm_needed': bool (Optional, check if clarification/confirmation needed)
            - 'check_file': str (Optional, filename to check existence of)
        """
        # print(f"\n--- Starting Conversation Flow ---")
        for step in flow:
            user_input = step['user']
    
            # --- NEW: Print Unicode code points ---
    
            # --- END NEW ---
            
            result = self.pipeline.run(user_input)
            ai_response = result.get("response", {}).get("text", "")
            # print(f"AI: {ai_response}")

            if "expected_ai" in step and step["expected_ai"]:
                self.assertIn(step["expected_ai"], ai_response)
            
            if "confirm_needed" in step:
                self.assertEqual(result.get("clarification_needed", False), step["confirm_needed"], 
                                 f"Clarification status mismatch for input: '{user_input}'. Expected {step['confirm_needed']}, got {result.get('clarification_needed', False)}")

            if "check_file" in step:
                file_path = os.path.join(self.test_ws, step["check_file"])
                self.assertTrue(os.path.exists(file_path), f"File {step['check_file']} should exist.")

    def test_scenario_1_slot_filling(self):
        """
        Scenario 1: Iterative Slot Filling (File Creation)
        User starts with broad intent, AI asks for details iteratively.
        """
        flow = [
            {"user": "ファイルを作って", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "test.txt", "expected_ai": "ファイルの内容を教えていただけますか？", "confirm_needed": True},
            {"user": "内容は『こんにちは』です", "expected_ai": "作成しました", "confirm_needed": False, "check_file": "test.txt"}
        ]
        self.run_conversation(flow)

    def test_scenario_2_safety_agree(self):
        """
        Scenario 2: Safety Confirmation - Agree
        User requests a command, AI asks for confirmation, User agrees, Action executed.
        """
        # Need to use a safe command that works on both Windows/Linux for testing
        cmd = "dir" if sys.platform == 'win32' else "ls -l"
        flow = [
            {"user": f"コマンド「{cmd}」を実行", "expected_ai": "よろしいですか？", "confirm_needed": True},
            {"user": "はい", "expected_ai": "コマンド実行結果", "confirm_needed": False}
        ]
        self.run_conversation(flow)

    def test_scenario_3_safety_disagree(self):
        """
        Scenario 3: Safety Confirmation - Disagree
        User requests a command, AI asks for confirmation, User agrees, Action executed.
        """
        flow = [
            {"user": "コマンド「rm -rf /」を実行", "expected_ai": "Safety Policy Error", "confirm_needed": False}
        ]
        self.run_conversation(flow)

    def test_scenario_4_context_reference(self):
        """
        Scenario 4: Contextual Reference
        User creates a file, then refers to it as 'it' (それ) to read it.
        """
        flow = [
            {"user": "「context_test.txt」を作成して。内容は「テスト」で。", "expected_ai": "作成しました", "confirm_needed": False, "check_file": "context_test.txt"},
            {"user": "それを読んで", "expected_ai": "テスト", "confirm_needed": False}
        ]
        self.run_conversation(flow)

    def test_scenario_5_interruption(self):
        """
        Scenario 5: Task Interruption and Resumption
        User starts a task, interrupts it with a question, and then resumes the task.
        """
        import datetime
        flow = [
            {"user": "ファイルを作って", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            # Interrupting intent (TIME/GENERAL)
                        {"user": "今何時？", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},            # Ideally task manager should still be active and waiting for filename?
            # Or does the new intent clear the task? 
            # Current Design: "Conversational intents should bypass..." but if task is active, TaskManager processes it.
            # If the input doesn't match a filename entity, it might be confusing.
            # BUT, TaskManager logic says: "If active task exists, new input... even if conversational... update state".
            # If "今何時？" is interpreted as filename, that's bad.
            # However, if it falls through to 'content', that's also bad.
            # We implemented specific logic: "If current intent is GREETING/TIME... and active task exists... flow through TaskManager".
            # Wait, our design update says: "Active task exists -> TaskManager receives input."
            # So the AI might try to use "今何時？" as the filename!
            # Let's see behavior. If it fails, that's a finding.
            
            # For this test, let's assume valid resumption inputs
            {"user": "interrupt_test.txt", "expected_ai": "ファイルの内容を教えていただけますか？", "confirm_needed": True},
            {"user": "内容は『Resumed』です", "expected_ai": "作成しました", "confirm_needed": False, "check_file": "interrupt_test.txt"}
        ]
        self.run_conversation(flow)

    def test_scenario_6_file_move(self):
        """
        Scenario 6: File Move
        Create a file, then move it.
        """
        # Setup
        with open(os.path.join(self.test_ws, "move_src.txt"), "w", encoding="utf-8") as f:
            f.write("test content")

        flow = [
            {"user": "move_src.txtをmove_dest.txtに移動して", "expected_ai": "移動します。よろしいですか？", "confirm_needed": True},
            {"user": "はい", "expected_ai": "移動しました", "confirm_needed": False, "check_file": "move_dest.txt"}
        ]
        self.run_conversation(flow)
        self.assertFalse(os.path.exists(os.path.join(self.test_ws, "move_src.txt")), "Source file should be gone.")

    def test_scenario_7_file_copy(self):
        """
        Scenario 7: File Copy
        Create a file, then copy it.
        """
        # Setup
        with open(os.path.join(self.test_ws, "copy_src.txt"), "w", encoding="utf-8") as f:
            f.write("test content")

        flow = [
            {"user": "copy_src.txtをcopy_dest.txtにコピーして", "expected_ai": "コピーしました", "confirm_needed": False, "check_file": "copy_dest.txt"}
        ]
        self.run_conversation(flow)
        self.assertTrue(os.path.exists(os.path.join(self.test_ws, "copy_src.txt")), "Source file should still exist.")

    def test_scenario_8_get_cwd(self):
        """
        Scenario 8: Get CWD
        Ask for current directory.
        """
        flow = [
            {"user": "今のパスを教えて", "expected_ai": "現在の作業ディレクトリ", "confirm_needed": False}
        ]
        self.run_conversation(flow)

    def test_scenario_9_compound_task_backup_delete(self):
        """Scenario 9: Compound Task - Backup and Delete"""
        # Setup: create the source file
        with open(os.path.join(self.test_ws, "compound_src.txt"), "w", encoding="utf-8") as f:
            f.write("source content")

        flow = [
            {"user": "compound_src.txt を compound_dest.txt にバックアップして削除して", "expected_ai": "バックアップして削除します。よろしいですか？"},
            {"user": "はい", "expected_ai": "完了しました。"}
        ]
        self.run_conversation(flow)
        self.assertFalse(os.path.exists(os.path.join(self.test_ws, "compound_src.txt")), "Source file should be deleted.")
        self.assertTrue(os.path.exists(os.path.join(self.test_ws, "compound_dest.txt")), "Destination file should exist.")

        # Verify: destination file exists and source file is deleted
        self.assertTrue(os.path.exists(os.path.join(self.test_ws, "compound_dest.txt")), "Destination file should exist.")
        self.assertFalse(os.path.exists(os.path.join(self.test_ws, "compound_src.txt")), "Source file should be deleted.")

if __name__ == "__main__":
    unittest.main(verbosity=2)

