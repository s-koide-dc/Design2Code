import unittest
import os
import shutil
import sys
import json
from src.pipeline_core.pipeline_core import Pipeline
from src.safety.safety_policy_validator import RiskLevel, SafetyCheckStatus, SafetyCheckResult
from src.utils.confirmation_response import (
    INTENT_AGREE,
    INTENT_CLARIFICATION_RESPONSE,
    INTENT_DISAGREE,
    STATE_AGREED,
    STATE_DISAGREED,
)
from src.utils.control_intents import (
    INTENT_BYE,
    INTENT_CAPABILITY,
    INTENT_DEFINITION,
    INTENT_GREETING,
    INTENT_PERSONAL_Q,
    INTENT_TIME,
    INTENT_WEATHER,
)

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
                        "examples": ["おはよう", "ハロー", "こんにちは", "やあ"]
                    },
                    {
                        "name": "BYE",
                        "patterns": [ {"pattern": "^(?:さようなら|バイバイ|またね|じゃあね)[！!？?]*$", "confidence_score": 0.95} ],
                        "examples": ["バイバイ", "またね", "じゃあね", "さようなら"]
                    },
                    {
                        "name": "AGREE",
                        "patterns": [ {"pattern": "^(?:はい|お願いします|了解|りょ|OK|おk)$", "confidence_score": 0.9} ],
                        "examples": ["そうですね", "OK", "はい", "了解"]
                    },
                    {
                        "name": "DISAGREE",
                        "patterns": [ {"pattern": "^(?:いいえ|違います|ノー|ダメ|拒否)$", "confidence_score": 0.9} ],
                        "examples": ["違います", "ノー", "いいえ", "キャンセル"]
                    },
                    {
                        "name": INTENT_TIME,
                        "patterns": [ {"pattern": "今何時？", "confidence_score": 0.9} ],
                        "examples": ["時間", "時計", "今何時？", "時間教えて", "今の時間"]
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
                        "examples": ["元気ですか", "調子いい？", "調子はどう？"]
                    },
                    {
                        "name": "EMOTIVE",
                        "patterns": [
                            {"pattern": "疲れた", "confidence_score": 0.9},
                            {"pattern": "しんどい", "confidence_score": 0.88}
                        ],
                        "examples": ["疲れたな", "しんどい", "へとへとです"]
                    },
                    {
                        "name": "SMALLTALK",
                        "patterns": [
                            {"pattern": "雑談", "confidence_score": 0.9},
                            {"pattern": "最近どう", "confidence_score": 0.88}
                        ],
                        "examples": ["雑談しよう", "最近どう？", "ちょっと話そう"]
                    },
                    {
                        "name": "FEEDBACK",
                        "patterns": [
                            {"pattern": "ありがとう", "confidence_score": 0.95},
                            {"pattern": "助かった", "confidence_score": 0.9}
                        ],
                        "examples": ["ありがとう", "助かったよ", "いい感じです"]
                    },
                    {
                        "name": "WEATHER",
                        "patterns": [
                            {"pattern": "天気", "confidence_score": 0.9},
                            {"pattern": "気温", "confidence_score": 0.85}
                        ],
                        "examples": ["今日の天気は？", "天気を教えて", "今日の気温は？"]
                    },
                    {
                        "name": "CAPABILITY",
                        "patterns": [
                            {"pattern": "何ができる", "confidence_score": 0.95},
                            {"pattern": "できること", "confidence_score": 0.95}
                        ],
                        "examples": ["何ができる？", "できることを教えて", "何を手伝える？"]
                    },
                    {
                        "name": "DEFINITION",
                        "patterns": [
                            {"pattern": ".+とは(?:何|なに|なん|何か|なんだ)", "confidence_score": 0.95},
                            {"pattern": ".+(?:の)?定義", "confidence_score": 0.9}
                        ],
                        "examples": ["AIとは何？", "クラスとは何？", "形態素解析の定義を教えて"]
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
                    },
                    {
                        "name": "EXECUTE_GOAL_DRIVEN_TDD",
                        "patterns": [
                            {"pattern": "TDDを実行", "confidence_score": 0.99},
                            {"pattern": "TDDで実装", "confidence_score": 0.99}
                        ],
                        "examples": ["TDDを実行して", "注文割引ロジックをTDDで実装して"]
                    },
                    {
                        "name": "ANALYZE_TEST_FAILURE",
                        "patterns": [
                            {"pattern": "失敗テストを分析", "confidence_score": 0.99},
                            {"pattern": "テスト失敗を分析", "confidence_score": 0.99}
                        ],
                        "examples": ["失敗テストを分析して", "テスト失敗を分析して"]
                    },
                    {
                        "name": "APPLY_CODE_FIX",
                        "patterns": [
                            {"pattern": "修正案を適用", "confidence_score": 0.99},
                            {"pattern": "コード修正を適用", "confidence_score": 0.99}
                        ],
                        "examples": ["修正案を適用して", "コード修正を適用して"]
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
                "EXECUTE_GOAL_DRIVEN_TDD": {
                    "states": ["INIT", "AWAITING_CRITERIA", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": ["goal_description", "acceptance_criteria"],
                    "transitions": {
                        "INIT": [
                            {
                                "condition": {
                                    "type": "all_of",
                                    "predicates": [
                                        { "type": "entity_exists", "key": "goal_description" },
                                        { "type": "entity_exists", "key": "acceptance_criteria" }
                                    ]
                                },
                                "next_state": "READY_FOR_EXECUTION"
                            },
                            {
                                "condition": { "type": "entity_exists", "key": "goal_description" },
                                "next_state": "AWAITING_CRITERIA"
                            }
                        ],
                        "AWAITING_CRITERIA": [
                            {
                                "condition": { "type": "entity_exists", "key": "acceptance_criteria" },
                                "next_state": "READY_FOR_EXECUTION"
                            }
                        ]
                    },
                    "clarification_messages": {
                        "goal_description": "TDDで実装したい内容を教えていただけますか？",
                        "acceptance_criteria": "受け入れ条件を教えていただけますか？"
                    }
                },
                "ANALYZE_TEST_FAILURE": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": [],
                    "transitions": {
                        "INIT": [
                            { "condition": { "type": "always_true" }, "next_state": "READY_FOR_EXECUTION" }
                        ]
                    }
                },
                "APPLY_CODE_FIX": {
                    "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                    "required_entities": [],
                    "transitions": {
                        "INIT": [
                            { "condition": { "type": "always_true" }, "next_state": "READY_FOR_EXECUTION" }
                        ]
                    }
                },
                INTENT_CLARIFICATION_RESPONSE: {
                    "states": ["INIT", STATE_AGREED, STATE_DISAGREED, "COMPLETED"],
                    "required_entities": ["user_response"],
                    "transitions": {
                        "INIT": [
                            {
                                "condition": { "type": "entity_value_is", "key": "user_response", "value": INTENT_AGREE },
                                "next_state": STATE_AGREED
                            },
                            {
                                "condition": { "type": "entity_value_is", "key": "user_response", "value": INTENT_DISAGREE },
                                "next_state": STATE_DISAGREED
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

    def _run_tdd_interruption_conversation_flow(
        self,
        first_user_input,
        first_intent,
        first_entities,
        expected_confirmation_text,
        expected_recommended_action,
        approved_result,
        expected_final_text,
        interruption_input="今何時？",
        interruption_intent=INTENT_TIME,
        interruption_entities=None,
        approval_input="はい"
    ):
        original_detect = self.pipeline.intent_detector.detect
        original_analyze = self.pipeline.semantic_analyzer.analyze
        original_validate = self.pipeline.planner.safety_validator.validate_action
        original_execute = self.pipeline.action_executor.execute
        session_id = "default_session"

        def detect_side_effect(context):
            if context["original_text"] == approval_input:
                context["analysis"] = {
                    "intent": INTENT_AGREE,
                    "intent_confidence": 0.99,
                    "entities": {}
                }
            elif context["original_text"] == interruption_input:
                context["analysis"] = {
                    "intent": interruption_intent,
                    "intent_confidence": 0.99,
                    "entities": interruption_entities or {}
                }
            else:
                context["analysis"] = {
                    "intent": first_intent,
                    "intent_confidence": 0.99,
                    "entities": dict(first_entities)
                }
            return context

        def validate_side_effect(action_method_name, plan_parameters, intent):
            if intent == first_intent:
                return SafetyCheckResult(
                    status=SafetyCheckStatus.OK,
                    risk_level=RiskLevel.HIGH,
                    message="承認が必要です。"
                )
            return original_validate(action_method_name, plan_parameters, intent)

        def execute_side_effect(context):
            return {
                **context,
                "action_result": dict(approved_result)
            }

        self.pipeline.intent_detector.detect = detect_side_effect
        self.pipeline.semantic_analyzer.analyze = lambda context: context
        self.pipeline.planner.safety_validator.validate_action = validate_side_effect
        self.pipeline.action_executor.execute = execute_side_effect

        try:
            first_result = self.pipeline.run(first_user_input)
            self.assertTrue(first_result.get("clarification_needed", False))
            self.assertEqual(first_result["task"]["recommended_action"], expected_recommended_action)
            self.assertEqual(first_result["plan"]["recommended_action"], expected_recommended_action)
            self.assertIn(expected_confirmation_text, first_result.get("response", {}).get("text", ""))

            interruption_result = self.pipeline.run(interruption_input)
            self.assertTrue(interruption_result.get("clarification_needed", False))
            self.assertIn(expected_confirmation_text, interruption_result.get("response", {}).get("text", ""))
            self.assertEqual(
                self.pipeline.task_manager.active_tasks[session_id]["recommended_action"],
                expected_recommended_action
            )

            approval_result = self.pipeline.run(approval_input)
            self.assertFalse(bool(approval_result.get("clarification_needed", False)))
            self.assertEqual(approval_result["plan"]["recommended_action"], expected_recommended_action)
            self.assertIn(expected_final_text, approval_result.get("response", {}).get("text", ""))
        finally:
            self.pipeline.intent_detector.detect = original_detect
            self.pipeline.semantic_analyzer.analyze = original_analyze
            self.pipeline.planner.safety_validator.validate_action = original_validate
            self.pipeline.action_executor.execute = original_execute
            self.pipeline.task_manager.reset_task(session_id)
            self.pipeline.context_manager.clear_pending_confirmation_plan(session_id)

    def _run_tdd_cancel_then_switch_conversation_flow(
        self,
        first_user_input,
        first_intent,
        first_entities,
        expected_confirmation_text,
        expected_recommended_action,
        switch_filename="resume.txt",
        switch_content="ok",
        reject_input="いいえ"
    ):
        original_detect = self.pipeline.intent_detector.detect
        original_analyze = self.pipeline.semantic_analyzer.analyze
        original_validate = self.pipeline.planner.safety_validator.validate_action
        session_id = "default_session"

        def detect_side_effect(context):
            original_text = context["original_text"]
            if original_text == reject_input:
                context["analysis"] = {
                    "intent": INTENT_DISAGREE,
                    "intent_confidence": 0.99,
                    "entities": {}
                }
            elif original_text == "ファイルを作って":
                context["analysis"] = {
                    "intent": "FILE_CREATE",
                    "intent_confidence": 0.99,
                    "entities": {}
                }
            elif original_text == switch_filename:
                context["analysis"] = {
                    "intent": "FILE_CREATE",
                    "intent_confidence": 0.99,
                    "entities": {"filename": {"value": switch_filename, "confidence": 0.99}}
                }
            elif original_text == f"内容は「{switch_content}」です":
                context["analysis"] = {
                    "intent": "PROVIDE_CONTENT",
                    "intent_confidence": 0.99,
                    "entities": {"content": {"value": switch_content, "confidence": 0.99}}
                }
            else:
                context["analysis"] = {
                    "intent": first_intent,
                    "intent_confidence": 0.99,
                    "entities": dict(first_entities)
                }
            return context

        def validate_side_effect(action_method_name, plan_parameters, intent):
            if intent == first_intent:
                return SafetyCheckResult(
                    status=SafetyCheckStatus.OK,
                    risk_level=RiskLevel.HIGH,
                    message="承認が必要です。"
                )
            return original_validate(action_method_name, plan_parameters, intent)

        self.pipeline.intent_detector.detect = detect_side_effect
        self.pipeline.semantic_analyzer.analyze = lambda context: context
        self.pipeline.planner.safety_validator.validate_action = validate_side_effect

        try:
            first_result = self.pipeline.run(first_user_input)
            self.assertTrue(first_result.get("clarification_needed", False))
            self.assertEqual(first_result["task"]["recommended_action"], expected_recommended_action)
            self.assertIn(expected_confirmation_text, first_result.get("response", {}).get("text", ""))

            reject_result = self.pipeline.run(reject_input)
            self.assertIn("キャンセル", reject_result.get("response", {}).get("text", ""))
            self.assertIsNone(self.pipeline.context_manager.get_pending_confirmation_plan(session_id))
            self.assertNotIn(session_id, self.pipeline.task_manager.active_tasks)

            new_task_result = self.pipeline.run("ファイルを作って")
            self.assertTrue(new_task_result.get("clarification_needed", False))
            self.assertIn("ファイル名を教えていただけますか？", new_task_result.get("response", {}).get("text", ""))

            filename_result = self.pipeline.run(switch_filename)
            self.assertTrue(filename_result.get("clarification_needed", False))
            self.assertIn("ファイルの内容を教えていただけますか？", filename_result.get("response", {}).get("text", ""))

            final_result = self.pipeline.run(f"内容は「{switch_content}」です")
            self.assertFalse(final_result.get("clarification_needed", False))
            self.assertIn("作成しました", final_result.get("response", {}).get("text", ""))
            self.assertEqual(final_result["task"]["name"], "FILE_CREATE")
        finally:
            self.pipeline.intent_detector.detect = original_detect
            self.pipeline.semantic_analyzer.analyze = original_analyze
            self.pipeline.planner.safety_validator.validate_action = original_validate
            self.pipeline.task_manager.reset_task(session_id)
            self.pipeline.context_manager.clear_pending_confirmation_plan(session_id)

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

    def test_scenario_10_tdd_interruption_and_resume(self):
        """Scenario 10: Goal-driven TDD confirmation survives conversational interruption."""
        self._run_tdd_interruption_conversation_flow(
            first_user_input="TDDを実行して",
            first_intent="EXECUTE_GOAL_DRIVEN_TDD",
            first_entities={
                "goal_description": {"value": "注文割引ロジックを実装", "confidence": 0.99},
                "acceptance_criteria": {"value": "合計金額に応じて割引率が変わる", "confidence": 0.99}
            },
            expected_confirmation_text="目標駆動TDDの実行を行います。",
            expected_recommended_action="execute_goal_driven_tdd",
            approved_result={
                "status": "success",
                "message": "TDDを実行しました",
                "dialogue_metadata": {
                    "phase": "goal_driven_tdd",
                    "goal_description": "注文割引ロジックを実装",
                    "iteration_count": 2,
                    "generated_code_count": 1,
                    "generated_test_count": 1
                }
            },
            expected_final_text="注文割引ロジックを実装 のTDD実行が完了しました。"
        )

    def test_scenario_11_failure_analysis_interruption_and_resume(self):
        """Scenario 11: Failure analysis confirmation survives conversational interruption."""
        self._run_tdd_interruption_conversation_flow(
            first_user_input="失敗テストを分析して",
            first_intent="ANALYZE_TEST_FAILURE",
            first_entities={},
            expected_confirmation_text="テスト失敗分析を行います。",
            expected_recommended_action="analyze_test_failure",
            approved_result={
                "status": "success",
                "message": "失敗テストを分析しました",
                "dialogue_metadata": {
                    "phase": "failure_analysis",
                    "primary_reason": "null参照が発生しています",
                    "primary_recommended_action": "apply_code_fix"
                }
            },
            expected_final_text="テスト失敗分析が完了しました。"
        )

    def test_scenario_12_apply_code_fix_interruption_and_resume(self):
        """Scenario 12: Code-fix confirmation survives conversational interruption."""
        self._run_tdd_interruption_conversation_flow(
            first_user_input="修正案を適用して",
            first_intent="APPLY_CODE_FIX",
            first_entities={},
            expected_confirmation_text="修正案の適用",
            expected_recommended_action="apply_code_fix",
            approved_result={
                "status": "success",
                "message": "修正案を適用しました",
                "dialogue_metadata": {
                    "phase": "code_fix",
                    "primary_reason": "境界条件の分岐が不足しています",
                    "primary_recommended_action": "run_related_tests"
                }
            },
            expected_final_text="コード修正の適用が完了しました。"
        )

    def test_scenario_13_tdd_new_task_request_does_not_replace_confirmation(self):
        """Scenario 13: Goal-driven TDD confirmation survives an explicit new task request."""
        self._run_tdd_interruption_conversation_flow(
            first_user_input="TDDを実行して",
            first_intent="EXECUTE_GOAL_DRIVEN_TDD",
            first_entities={
                "goal_description": {"value": "注文割引ロジックを実装", "confidence": 0.99},
                "acceptance_criteria": {"value": "合計金額に応じて割引率が変わる", "confidence": 0.99}
            },
            expected_confirmation_text="目標駆動TDDの実行を行います。",
            expected_recommended_action="execute_goal_driven_tdd",
            approved_result={
                "status": "success",
                "message": "TDDを実行しました",
                "dialogue_metadata": {
                    "phase": "goal_driven_tdd",
                    "goal_description": "注文割引ロジックを実装",
                    "iteration_count": 2,
                    "generated_code_count": 1,
                    "generated_test_count": 1
                }
            },
            expected_final_text="注文割引ロジックを実装 のTDD実行が完了しました。",
            interruption_input="ファイルを作って",
            interruption_intent="FILE_CREATE",
            interruption_entities={}
        )

    def test_scenario_14_failure_analysis_new_task_request_does_not_replace_confirmation(self):
        """Scenario 14: Failure analysis confirmation survives an explicit new task request."""
        self._run_tdd_interruption_conversation_flow(
            first_user_input="失敗テストを分析して",
            first_intent="ANALYZE_TEST_FAILURE",
            first_entities={},
            expected_confirmation_text="テスト失敗分析を行います。",
            expected_recommended_action="analyze_test_failure",
            approved_result={
                "status": "success",
                "message": "失敗テストを分析しました",
                "dialogue_metadata": {
                    "phase": "failure_analysis",
                    "primary_reason": "null参照が発生しています",
                    "primary_recommended_action": "apply_code_fix"
                }
            },
            expected_final_text="テスト失敗分析が完了しました。",
            interruption_input="ファイルを作って",
            interruption_intent="FILE_CREATE",
            interruption_entities={}
        )

    def test_scenario_15_apply_code_fix_new_task_request_does_not_replace_confirmation(self):
        """Scenario 15: Code-fix confirmation survives an explicit new task request."""
        self._run_tdd_interruption_conversation_flow(
            first_user_input="修正案を適用して",
            first_intent="APPLY_CODE_FIX",
            first_entities={},
            expected_confirmation_text="修正案の適用",
            expected_recommended_action="apply_code_fix",
            approved_result={
                "status": "success",
                "message": "修正案を適用しました",
                "dialogue_metadata": {
                    "phase": "code_fix",
                    "primary_reason": "境界条件の分岐が不足しています",
                    "primary_recommended_action": "run_related_tests"
                }
            },
            expected_final_text="コード修正の適用が完了しました。",
            interruption_input="ファイルを作って",
            interruption_intent="FILE_CREATE",
            interruption_entities={}
        )

    def test_scenario_16_tdd_disagree_then_switch_to_new_task(self):
        """Scenario 16: Rejecting TDD confirmation allows a fresh file task to start."""
        self._run_tdd_cancel_then_switch_conversation_flow(
            first_user_input="TDDを実行して",
            first_intent="EXECUTE_GOAL_DRIVEN_TDD",
            first_entities={
                "goal_description": {"value": "注文割引ロジックを実装", "confidence": 0.99},
                "acceptance_criteria": {"value": "合計金額に応じて割引率が変わる", "confidence": 0.99}
            },
            expected_confirmation_text="目標駆動TDDの実行を行います。",
            expected_recommended_action="execute_goal_driven_tdd"
        )

    def test_scenario_17_failure_analysis_disagree_then_switch_to_new_task(self):
        """Scenario 17: Rejecting failure analysis confirmation allows a fresh file task to start."""
        self._run_tdd_cancel_then_switch_conversation_flow(
            first_user_input="失敗テストを分析して",
            first_intent="ANALYZE_TEST_FAILURE",
            first_entities={},
            expected_confirmation_text="テスト失敗分析を行います。",
            expected_recommended_action="analyze_test_failure"
        )

    def test_scenario_18_apply_code_fix_disagree_then_switch_to_new_task(self):
        """Scenario 18: Rejecting code-fix confirmation allows a fresh file task to start."""
        self._run_tdd_cancel_then_switch_conversation_flow(
            first_user_input="修正案を適用して",
            first_intent="APPLY_CODE_FIX",
            first_entities={},
            expected_confirmation_text="修正案の適用",
            expected_recommended_action="apply_code_fix"
        )

    def test_scenario_19_compound_task_new_task_request_does_not_replace_confirmation(self):
        """Scenario 19: Compound-task approval survives an explicit new task request."""
        with open(os.path.join(self.test_ws, "compound_src.txt"), "w", encoding="utf-8") as f:
            f.write("source content")

        first_result = self.pipeline.run("compound_src.txt を compound_dest.txt にバックアップして削除して")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("バックアップして削除します。よろしいですか？", first_result.get("response", {}).get("text", ""))
        self.assertEqual(self.pipeline.task_manager.active_tasks["default_session"]["name"], "BACKUP_AND_DELETE")

        interruption_result = self.pipeline.run("ファイルを作って")
        self.assertTrue(interruption_result.get("clarification_needed", False))
        self.assertIn("バックアップして削除します。よろしいですか？", interruption_result.get("response", {}).get("text", ""))
        self.assertEqual(self.pipeline.task_manager.active_tasks["default_session"]["name"], "BACKUP_AND_DELETE")

    def test_scenario_20_compound_task_disagree_then_switch_to_new_task(self):
        """Scenario 20: Rejecting compound-task approval allows a fresh file task to start."""
        with open(os.path.join(self.test_ws, "compound_src.txt"), "w", encoding="utf-8") as f:
            f.write("source content")

        first_result = self.pipeline.run("compound_src.txt を compound_dest.txt にバックアップして削除して")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("バックアップして削除します。よろしいですか？", first_result.get("response", {}).get("text", ""))

        reject_result = self.pipeline.run("いいえ")
        self.assertIn("キャンセル", reject_result.get("response", {}).get("text", ""))
        self.assertNotIn("default_session", self.pipeline.task_manager.active_tasks)

        new_task_result = self.pipeline.run("ファイルを作って")
        self.assertTrue(new_task_result.get("clarification_needed", False))
        self.assertIn("ファイル名を教えていただけますか？", new_task_result.get("response", {}).get("text", ""))

        filename_result = self.pipeline.run("resume.txt")
        self.assertTrue(filename_result.get("clarification_needed", False))
        self.assertIn("ファイルの内容を教えていただけますか？", filename_result.get("response", {}).get("text", ""))

        final_result = self.pipeline.run("内容は「ok」です")
        self.assertFalse(bool(final_result.get("clarification_needed", False)))
        self.assertIn("作成しました", final_result.get("response", {}).get("text", ""))
        self.assertEqual(final_result["task"]["name"], "FILE_CREATE")

    def test_scenario_21_compound_task_agree_variant_executes_with_ryokai(self):
        """Scenario 21: Compound-task approval accepts the agree variant '了解'."""
        with open(os.path.join(self.test_ws, "variant_src.txt"), "w", encoding="utf-8") as f:
            f.write("source content")

        first_result = self.pipeline.run("variant_src.txt を variant_dest.txt にバックアップして削除して")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("バックアップして削除します。よろしいですか？", first_result.get("response", {}).get("text", ""))

        approve_result = self.pipeline.run("了解")
        self.assertFalse(bool(approve_result.get("clarification_needed", False)))
        self.assertIn("完了しました。", approve_result.get("response", {}).get("text", ""))
        self.assertTrue(os.path.exists(os.path.join(self.test_ws, "variant_dest.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.test_ws, "variant_src.txt")))

    def test_scenario_22_compound_task_disagree_variant_cancels_with_no(self):
        """Scenario 22: Compound-task approval accepts the disagree variant 'ノー'."""
        with open(os.path.join(self.test_ws, "variant_src_no.txt"), "w", encoding="utf-8") as f:
            f.write("source content")

        first_result = self.pipeline.run("variant_src_no.txt を variant_dest_no.txt にバックアップして削除して")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("バックアップして削除します。よろしいですか？", first_result.get("response", {}).get("text", ""))

        reject_result = self.pipeline.run("ノー")
        self.assertIn("キャンセル", reject_result.get("response", {}).get("text", ""))
        self.assertNotIn("default_session", self.pipeline.task_manager.active_tasks)
        self.assertTrue(os.path.exists(os.path.join(self.test_ws, "variant_src_no.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.test_ws, "variant_dest_no.txt")))

    def test_scenario_23_cmd_run_agree_variant_executes_with_ryokai(self):
        """Scenario 23: Command confirmation accepts the agree variant '了解'."""
        cmd = "dir" if sys.platform == 'win32' else "ls -l"
        flow = [
            {"user": f"コマンド「{cmd}」を実行", "expected_ai": "よろしいですか？", "confirm_needed": True},
            {"user": "了解", "expected_ai": "コマンド実行結果", "confirm_needed": False}
        ]
        self.run_conversation(flow)

    def test_scenario_24_cmd_run_disagree_variant_cancels_with_cancel(self):
        """Scenario 24: Command confirmation accepts the disagree variant 'キャンセル'."""
        cmd = "dir" if sys.platform == 'win32' else "ls -l"
        flow = [
            {"user": f"コマンド「{cmd}」を実行", "expected_ai": "よろしいですか？", "confirm_needed": True},
            {"user": "キャンセル", "expected_ai": "キャンセル", "confirm_needed": False}
        ]
        self.run_conversation(flow)

    def test_scenario_25_tdd_agree_variant_executes_with_ryokai(self):
        """Scenario 25: Goal-driven TDD confirmation accepts the agree variant '了解'."""
        self._run_tdd_interruption_conversation_flow(
            first_user_input="TDDを実行して",
            first_intent="EXECUTE_GOAL_DRIVEN_TDD",
            first_entities={
                "goal_description": {"value": "注文割引ロジックを実装", "confidence": 0.99},
                "acceptance_criteria": {"value": "合計金額に応じて割引率が変わる", "confidence": 0.99}
            },
            expected_confirmation_text="目標駆動TDDの実行を行います。",
            expected_recommended_action="execute_goal_driven_tdd",
            approved_result={
                "status": "success",
                "message": "TDDを実行しました",
                "dialogue_metadata": {
                    "phase": "goal_driven_tdd",
                    "goal_description": "注文割引ロジックを実装",
                    "iteration_count": 2,
                    "generated_code_count": 1,
                    "generated_test_count": 1
                }
            },
            expected_final_text="注文割引ロジックを実装 のTDD実行が完了しました。",
            approval_input="了解"
        )

    def test_scenario_26_failure_analysis_agree_variant_executes_with_ryokai(self):
        """Scenario 26: Failure analysis confirmation accepts the agree variant '了解'."""
        self._run_tdd_interruption_conversation_flow(
            first_user_input="失敗テストを分析して",
            first_intent="ANALYZE_TEST_FAILURE",
            first_entities={},
            expected_confirmation_text="テスト失敗分析を行います。",
            expected_recommended_action="analyze_test_failure",
            approved_result={
                "status": "success",
                "message": "失敗テストを分析しました",
                "dialogue_metadata": {
                    "phase": "failure_analysis",
                    "primary_reason": "null参照が発生しています",
                    "primary_recommended_action": "apply_code_fix"
                }
            },
            expected_final_text="テスト失敗分析が完了しました。",
            approval_input="了解"
        )

    def test_scenario_27_apply_code_fix_agree_variant_executes_with_ryokai(self):
        """Scenario 27: Code-fix confirmation accepts the agree variant '了解'."""
        self._run_tdd_interruption_conversation_flow(
            first_user_input="修正案を適用して",
            first_intent="APPLY_CODE_FIX",
            first_entities={},
            expected_confirmation_text="修正案の適用",
            expected_recommended_action="apply_code_fix",
            approved_result={
                "status": "success",
                "message": "修正案を適用しました",
                "dialogue_metadata": {
                    "phase": "code_fix",
                    "primary_reason": "境界条件の分岐が不足しています",
                    "primary_recommended_action": "run_related_tests"
                }
            },
            expected_final_text="コード修正の適用が完了しました。",
            approval_input="了解"
        )

    def test_scenario_28_tdd_disagree_variant_cancels_with_cancel(self):
        """Scenario 28: Goal-driven TDD confirmation accepts the disagree variant 'キャンセル'."""
        self._run_tdd_cancel_then_switch_conversation_flow(
            first_user_input="TDDを実行して",
            first_intent="EXECUTE_GOAL_DRIVEN_TDD",
            first_entities={
                "goal_description": {"value": "注文割引ロジックを実装", "confidence": 0.99},
                "acceptance_criteria": {"value": "合計金額に応じて割引率が変わる", "confidence": 0.99}
            },
            expected_confirmation_text="目標駆動TDDの実行を行います。",
            expected_recommended_action="execute_goal_driven_tdd",
            reject_input="キャンセル"
        )

    def test_scenario_29_file_create_survives_greeting_variant_interruption(self):
        """Scenario 29: Active file-creation clarification survives a greeting variant."""
        flow = [
            {"user": "ファイルを作って", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "ハロー", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "variant_greeting.txt", "expected_ai": "ファイルの内容を教えていただけますか？", "confirm_needed": True},
            {"user": "内容は「hello」です", "expected_ai": "作成しました", "confirm_needed": False, "check_file": "variant_greeting.txt"}
        ]
        self.run_conversation(flow)

    def test_scenario_30_file_create_survives_time_variant_interruption(self):
        """Scenario 30: Active file-creation clarification survives a time-query variant."""
        flow = [
            {"user": "ファイルを作って", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "時間教えて", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "variant_time.txt", "expected_ai": "ファイルの内容を教えていただけますか？", "confirm_needed": True},
            {"user": "内容は「clock」です", "expected_ai": "作成しました", "confirm_needed": False, "check_file": "variant_time.txt"}
        ]
        self.run_conversation(flow)

    def test_scenario_31_cmd_run_confirmation_survives_greeting_variant(self):
        """Scenario 31: Command confirmation survives a greeting variant and still executes after approval."""
        cmd = "dir" if sys.platform == 'win32' else "ls -l"
        first_result = self.pipeline.run(f"コマンド「{cmd}」を実行")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", first_result.get("response", {}).get("text", ""))

        interruption_result = self.pipeline.run("ハロー")
        self.assertTrue(interruption_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", interruption_result.get("response", {}).get("text", ""))

        analysis = interruption_result.get("analysis", {})
        self.assertEqual(analysis.get("intent"), INTENT_GREETING)

        approve_result = self.pipeline.run("了解")
        self.assertFalse(bool(approve_result.get("clarification_needed", False)))
        self.assertIn("コマンド実行結果", approve_result.get("response", {}).get("text", ""))

    def test_scenario_32_compound_confirmation_survives_time_variant(self):
        """Scenario 32: Compound-task confirmation survives a time-query variant and still executes after approval."""
        with open(os.path.join(self.test_ws, "variant_time_src.txt"), "w", encoding="utf-8") as f:
            f.write("source content")

        first_result = self.pipeline.run("variant_time_src.txt を variant_time_dest.txt にバックアップして削除して")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("バックアップして削除します。よろしいですか？", first_result.get("response", {}).get("text", ""))

        interruption_result = self.pipeline.run("時間教えて")
        self.assertTrue(interruption_result.get("clarification_needed", False))
        self.assertIn("バックアップして削除します。よろしいですか？", interruption_result.get("response", {}).get("text", ""))

        analysis = interruption_result.get("analysis", {})
        self.assertEqual(analysis.get("intent"), INTENT_TIME)

        approve_result = self.pipeline.run("了解")
        self.assertFalse(bool(approve_result.get("clarification_needed", False)))
        self.assertIn("完了しました。", approve_result.get("response", {}).get("text", ""))
        self.assertTrue(os.path.exists(os.path.join(self.test_ws, "variant_time_dest.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.test_ws, "variant_time_src.txt")))

    def test_scenario_33_file_create_survives_personal_q_variant_interruption(self):
        """Scenario 33: Active file-creation clarification survives a personal-question variant."""
        flow = [
            {"user": "ファイルを作って", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "調子はどう？", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "variant_personal.txt", "expected_ai": "ファイルの内容を教えていただけますか？", "confirm_needed": True},
            {"user": "内容は「status」です", "expected_ai": "作成しました", "confirm_needed": False, "check_file": "variant_personal.txt"}
        ]
        self.run_conversation(flow)

    def test_scenario_34_file_create_survives_bye_variant_interruption(self):
        """Scenario 34: Active file-creation clarification survives a bye variant."""
        flow = [
            {"user": "ファイルを作って", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "バイバイ", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "variant_bye.txt", "expected_ai": "ファイルの内容を教えていただけますか？", "confirm_needed": True},
            {"user": "内容は「bye」です", "expected_ai": "作成しました", "confirm_needed": False, "check_file": "variant_bye.txt"}
        ]
        self.run_conversation(flow)

    def test_scenario_35_cmd_run_confirmation_survives_personal_q_variant(self):
        """Scenario 35: Command confirmation survives a personal-question variant."""
        cmd = "dir" if sys.platform == 'win32' else "ls -l"
        first_result = self.pipeline.run(f"コマンド「{cmd}」を実行")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", first_result.get("response", {}).get("text", ""))

        interruption_result = self.pipeline.run("調子はどう？")
        self.assertTrue(interruption_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", interruption_result.get("response", {}).get("text", ""))
        self.assertEqual(interruption_result.get("analysis", {}).get("intent"), INTENT_PERSONAL_Q)

        approve_result = self.pipeline.run("了解")
        self.assertFalse(bool(approve_result.get("clarification_needed", False)))
        self.assertIn("コマンド実行結果", approve_result.get("response", {}).get("text", ""))

    def test_scenario_36_cmd_run_confirmation_survives_bye_variant(self):
        """Scenario 36: Command confirmation survives a bye variant."""
        cmd = "dir" if sys.platform == 'win32' else "ls -l"
        first_result = self.pipeline.run(f"コマンド「{cmd}」を実行")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", first_result.get("response", {}).get("text", ""))

        interruption_result = self.pipeline.run("バイバイ")
        self.assertTrue(interruption_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", interruption_result.get("response", {}).get("text", ""))
        self.assertEqual(interruption_result.get("analysis", {}).get("intent"), INTENT_BYE)

        approve_result = self.pipeline.run("了解")
        self.assertFalse(bool(approve_result.get("clarification_needed", False)))
        self.assertIn("コマンド実行結果", approve_result.get("response", {}).get("text", ""))

    def test_scenario_37_file_create_survives_weather_variant_interruption(self):
        """Scenario 37: Active file-creation clarification survives a weather variant."""
        flow = [
            {"user": "ファイルを作って", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "今日の天気は？", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "variant_weather.txt", "expected_ai": "ファイルの内容を教えていただけますか？", "confirm_needed": True},
            {"user": "内容は「sunny」です", "expected_ai": "作成しました", "confirm_needed": False, "check_file": "variant_weather.txt"}
        ]
        self.run_conversation(flow)

    def test_scenario_38_file_create_survives_capability_variant_interruption(self):
        """Scenario 38: Active file-creation clarification survives a capability variant."""
        flow = [
            {"user": "ファイルを作って", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "何ができる？", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "variant_capability.txt", "expected_ai": "ファイルの内容を教えていただけますか？", "confirm_needed": True},
            {"user": "内容は「skills」です", "expected_ai": "作成しました", "confirm_needed": False, "check_file": "variant_capability.txt"}
        ]
        self.run_conversation(flow)

    def test_scenario_39_file_create_survives_definition_variant_interruption(self):
        """Scenario 39: Active file-creation clarification survives a definition variant."""
        flow = [
            {"user": "ファイルを作って", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "AIとは何？", "expected_ai": "ファイル名を教えていただけますか？", "confirm_needed": True},
            {"user": "variant_definition.txt", "expected_ai": "ファイルの内容を教えていただけますか？", "confirm_needed": True},
            {"user": "内容は「meaning」です", "expected_ai": "作成しました", "confirm_needed": False, "check_file": "variant_definition.txt"}
        ]
        self.run_conversation(flow)

    def test_scenario_40_cmd_run_confirmation_survives_weather_variant(self):
        """Scenario 40: Command confirmation survives a weather variant."""
        cmd = "dir" if sys.platform == 'win32' else "ls -l"
        first_result = self.pipeline.run(f"コマンド「{cmd}」を実行")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", first_result.get("response", {}).get("text", ""))

        interruption_result = self.pipeline.run("今日の天気は？")
        self.assertTrue(interruption_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", interruption_result.get("response", {}).get("text", ""))
        self.assertEqual(interruption_result.get("analysis", {}).get("intent"), INTENT_WEATHER)

        approve_result = self.pipeline.run("了解")
        self.assertFalse(bool(approve_result.get("clarification_needed", False)))
        self.assertIn("コマンド実行結果", approve_result.get("response", {}).get("text", ""))

    def test_scenario_41_cmd_run_confirmation_survives_capability_variant(self):
        """Scenario 41: Command confirmation survives a capability variant."""
        cmd = "dir" if sys.platform == 'win32' else "ls -l"
        first_result = self.pipeline.run(f"コマンド「{cmd}」を実行")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", first_result.get("response", {}).get("text", ""))

        interruption_result = self.pipeline.run("何ができる？")
        self.assertTrue(interruption_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", interruption_result.get("response", {}).get("text", ""))
        self.assertEqual(interruption_result.get("analysis", {}).get("intent"), INTENT_CAPABILITY)

        approve_result = self.pipeline.run("了解")
        self.assertFalse(bool(approve_result.get("clarification_needed", False)))
        self.assertIn("コマンド実行結果", approve_result.get("response", {}).get("text", ""))

    def test_scenario_42_cmd_run_confirmation_survives_definition_variant(self):
        """Scenario 42: Command confirmation survives a definition variant."""
        cmd = "dir" if sys.platform == 'win32' else "ls -l"
        first_result = self.pipeline.run(f"コマンド「{cmd}」を実行")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", first_result.get("response", {}).get("text", ""))

        interruption_result = self.pipeline.run("AIとは何？")
        self.assertTrue(interruption_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", interruption_result.get("response", {}).get("text", ""))
        self.assertEqual(interruption_result.get("analysis", {}).get("intent"), INTENT_DEFINITION)

        approve_result = self.pipeline.run("了解")
        self.assertFalse(bool(approve_result.get("clarification_needed", False)))
        self.assertIn("コマンド実行結果", approve_result.get("response", {}).get("text", ""))

    def test_scenario_43_file_create_survives_emotive_variant_with_response(self):
        """Scenario 43: Active file-creation clarification survives an emotive turn and returns the emotive response."""
        first_result = self.pipeline.run("ファイルを作って")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("ファイル名を教えていただけますか？", first_result.get("response", {}).get("text", ""))

        interruption_result = self.pipeline.run("疲れたな")
        self.assertTrue(interruption_result.get("clarification_needed", False))
        self.assertIn("ファイル名を教えていただけますか？", interruption_result.get("response", {}).get("text", ""))
        self.assertEqual(interruption_result.get("analysis", {}).get("intent"), "EMOTIVE")
        self.assertIn("元の作業に戻るため", interruption_result.get("response", {}).get("text", ""))

    def test_scenario_44_cmd_run_confirmation_survives_smalltalk_variant_with_response(self):
        """Scenario 44: Command confirmation survives a smalltalk turn and re-shows the confirmation prompt."""
        cmd = "dir" if sys.platform == 'win32' else "ls -l"
        first_result = self.pipeline.run(f"コマンド「{cmd}」を実行")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", first_result.get("response", {}).get("text", ""))

        interruption_result = self.pipeline.run("雑談しよう")
        self.assertTrue(interruption_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", interruption_result.get("response", {}).get("text", ""))
        self.assertEqual(interruption_result.get("analysis", {}).get("intent"), "SMALLTALK")

    def test_scenario_45_cmd_run_confirmation_survives_feedback_variant_with_response(self):
        """Scenario 45: Command confirmation survives feedback and re-shows the confirmation prompt."""
        cmd = "dir" if sys.platform == 'win32' else "ls -l"
        first_result = self.pipeline.run(f"コマンド「{cmd}」を実行")
        self.assertTrue(first_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", first_result.get("response", {}).get("text", ""))

        interruption_result = self.pipeline.run("ありがとう")
        self.assertTrue(interruption_result.get("clarification_needed", False))
        self.assertIn("よろしいですか？", interruption_result.get("response", {}).get("text", ""))
        self.assertEqual(interruption_result.get("analysis", {}).get("intent"), "FEEDBACK")

if __name__ == "__main__":
    unittest.main(verbosity=2)

