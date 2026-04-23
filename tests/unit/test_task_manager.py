import unittest
import os
import json
import shutil # Import shutil
from unittest.mock import MagicMock, patch

from src.task_manager.task_manager import TaskManager
from src.action_executor.action_executor import ActionExecutor
from tests.fixtures.task_definitions import get_test_definitions

class TestTaskManager(unittest.TestCase):

    def setUp(self):
        self.mock_action_executor = MagicMock(spec=ActionExecutor)

        # 共通のテスト定義を使用
        mock_task_definitions = get_test_definitions()

        # Patch _load_task_definitions to return our mock definitions
        self.patcher_load_defs = patch.object(TaskManager, '_load_task_definitions', return_value=mock_task_definitions)
        self.mock_load_defs = self.patcher_load_defs.start()

        # ConfigManagerのモック
        self.mock_config_manager = MagicMock()
        self.mock_config_manager.get_section.return_value = {
            "enable_persistence": False,
            "persistence_dir": "data/task_states",
            "max_state_age_hours": 24,
            "max_active_sessions": 100,
            "session_timeout_minutes": 60,
            "debug_mode": False,
            "log_state_transitions": False,
            "max_recovery_attempts": 3
        }
        self.mock_config_manager.get_safety_policy.return_value = {
            "destructive_intents": ["FILE_DELETE", "CMD_RUN"]
        }
        self.mock_config_manager.task_definitions_path = "resources/task_definitions.json"

        # メトリクスとパーシスタンスのモック
        self.patcher_metrics = patch('src.task_manager.metrics.TaskManagerMetrics')
        self.mock_metrics_class = self.patcher_metrics.start()
        self.mock_metrics = MagicMock()
        self.mock_metrics_class.return_value = self.mock_metrics

        self.patcher_persistence = patch('src.task_manager.task_persistence.TaskPersistence')
        self.mock_persistence_class = self.patcher_persistence.start()
        self.mock_persistence = MagicMock()
        self.mock_persistence_class.return_value = self.mock_persistence

        self.tm = TaskManager(action_executor=self.mock_action_executor, 
                              task_definitions_path="ignored_path.json",
                              config_manager=self.mock_config_manager)

    def tearDown(self):
        self.patcher_load_defs.stop()
        self.patcher_metrics.stop()
        self.patcher_persistence.stop()

    def test_start_file_create_task_filename_provided(self):
        context = {
            "session_id": "test_session_1",
            "original_text": "hello.txt を作って",
            "analysis": {
                "intent": "FILE_CREATE",
                "entities": {
                    "filename": {"value": "hello.txt", "confidence": 0.9}
                }
            }
        }
        result = self.tm.manage_task_state(context)
        self.assertIn("task", result)
        self.assertEqual(result["task"]["name"], "FILE_CREATE")
        self.assertEqual(result["task"]["state"], "AWAITING_CONTENT")
        self.assertEqual(result["task"]["parameters"]["filename"]["value"], "hello.txt")

    def test_continue_file_create_task_content_provided(self):
        # Simulate initial state
        initial_context = {
            "session_id": "test_session_2",
            "original_text": "hello.txt を作って",
            "analysis": {
                "intent": "FILE_CREATE",
                "entities": {
                    "filename": {"value": "hello.txt", "confidence": 0.9}
                }
            }
        }
        self.tm.manage_task_state(initial_context)

        # Provide content
        context = {
            "session_id": "test_session_2",
            "original_text": "内容は Hello です",
            "analysis": {
                "intent": "FILE_CREATE",
                "entities": {
                    "content": {"value": "Hello", "confidence": 0.9}
                }
            }
        }
        result = self.tm.manage_task_state(context)
        self.assertIn("task", result)
        self.assertEqual(result["task"]["name"], "FILE_CREATE")
        self.assertEqual(result["task"]["state"], "READY_FOR_EXECUTION")
        self.assertEqual(result["task"]["parameters"]["content"]["value"], "Hello")

    def test_new_task_all_entities_provided_at_once(self):
        context = {
            "session_id": "test_session_3",
            "original_text": "新しいファイル new.txt を作って内容は world です",
            "analysis": {
                "intent": "FILE_CREATE",
                "entities": {"filename": {"value": "new.txt", "confidence": 0.9}, "content": {"value": "world", "confidence": 0.9}}
            }
        }
        result = self.tm.manage_task_state(context)
        self.assertIn("task", result)
        self.assertEqual(result["task"]["name"], "FILE_CREATE")
        self.assertEqual(result["task"]["state"], "READY_FOR_EXECUTION")
        self.assertEqual(result["task"]["parameters"]["filename"]["value"], "new.txt")
        self.assertEqual(result["task"]["parameters"]["content"]["value"], "world")

    def test_task_reset(self):
        context = {
            "session_id": "test_session_4",
            "original_text": "タスクを開始",
            "analysis": {
                "intent": "FILE_CREATE",
                "entities": {"filename": {"value": "reset.txt", "confidence": 0.9}}
            }
        }
        result = self.tm.manage_task_state(context)
        self.assertEqual(result["task"]["parameters"]["filename"]["value"], "reset.txt")
        self.assertIn("test_session_4", self.tm.active_tasks)
        
        self.tm.reset_task("test_session_4")
        self.assertNotIn("test_session_4", self.tm.active_tasks)

    def test_no_task_definition(self):
        context = {
            "session_id": "test_session_5",
            "original_text": "未知のタスク",
            "analysis": {
                "intent": "UNKNOWN_INTENT",
                "entities": {}
            }
        }
        result = self.tm.manage_task_state(context)
        self.assertNotIn("task", result)
        self.assertIn("errors", result)
        self.assertGreater(len(result["errors"]), 0) # Assert that errors list is not empty
        self.assertIn("タスク定義 'UNKNOWN_INTENT' が見つかりません。", result["errors"][0]["message"])

    def test_compound_task_full_lifecycle(self):
        # 1. Setup: Expand mock definitions to include the compound task and its children
        self.mock_load_defs.return_value.update({
            "BACKUP_AND_DELETE": {
                "type": "COMPOUND_TASK",
                "require_overall_approval": False,  # Disable overall approval for this test
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
                "required_entities": ["source_filename", "destination_filename"]
            },
            "FILE_COPY": {
                "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                "required_entities": ["source_filename", "destination_filename"],
                "transitions": {
                    "INIT": [{"condition": {"type": "all_of", "predicates": [{"type": "entity_exists", "key": "source_filename"}, {"type": "entity_exists", "key": "destination_filename"}]}, "next_state": "READY_FOR_EXECUTION"}]
                }
            },
            "FILE_DELETE": {
                "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                "required_entities": ["filename"],
                "transitions": {
                    "INIT": [{"condition": {"type": "entity_exists", "key": "filename"}, "next_state": "READY_FOR_EXECUTION"}]
                }
            }
        })
        self.tm = TaskManager(action_executor=self.mock_action_executor) # Re-initialize with updated defs

        # 2. Initial call to start the compound task
        context = {
            "session_id": "compound_session_1",
            "analysis": {
                "intent": "BACKUP_AND_DELETE",
                "entities": {
                    "source_filename": {"value": "a.txt", "confidence": 0.9},
                    "destination_filename": {"value": "b.txt", "confidence": 0.9}
                }
            }
        }
        result = self.tm.manage_task_state(context)

        # 3. Verify the first subtask (FILE_COPY) is ready
        self.assertIn("task", result)
        task = result["task"]
        self.assertEqual(task["name"], "BACKUP_AND_DELETE")
        self.assertEqual(task["type"], "COMPOUND_TASK")
        self.assertEqual(len(task["subtasks"]), 2)
        self.assertEqual(task["current_subtask_index"], 0)
        
        sub_task_1 = task["subtasks"][0]
        self.assertEqual(sub_task_1["name"], "FILE_COPY")
        self.assertEqual(sub_task_1["state"], "READY_FOR_EXECUTION")
        self.assertEqual(sub_task_1["parameters"]["source_filename"]["value"], "a.txt")
        self.assertEqual(sub_task_1["parameters"]["destination_filename"]["value"], "b.txt")

        # 4. Execute the first subtask and update state
        context["action_result"] = {"status": "success"}
        result = self.tm.update_task_after_execution(context)
        
        # 5. Verify the second subtask (FILE_DELETE) is now ready
        # The task is still active, so we call manage_task_state again
        # Clear the entities from the previous user input
        context["analysis"]["entities"] = {}
        result = self.tm.manage_task_state(context) 
        
        task = result["task"]
        self.assertEqual(task["current_subtask_index"], 1)
        sub_task_2 = task["subtasks"][1]
        self.assertEqual(sub_task_2["name"], "FILE_DELETE")
        self.assertEqual(sub_task_2["state"], "READY_FOR_EXECUTION")
        # Ensure correct parameters are propagated. FILE_DELETE only needs source_filename
        self.assertEqual(sub_task_2["parameters"]["filename"]["value"], "a.txt")

        # 6. Execute the second subtask and update state
        context["action_result"] = {"status": "success"}
        result = self.tm.update_task_after_execution(context)

        # 7. Verify the entire compound task is now complete
        # After completion, the task is removed from active tasks
        self.assertNotIn("compound_session_1", self.tm.active_tasks)

    def test_compound_task_overall_approval_request(self):
        context = {
            "session_id": "overall_approval_session",
            "analysis": {
                "intent": "BACKUP_AND_DELETE",
                "entities": {
                    "source_filename": {"value": "orig.txt", "confidence": 0.9},
                    "destination_filename": {"value": "backup.txt", "confidence": 0.9}
                }
            }
        }
        result = self.tm.manage_task_state(context)
        self.assertIn("task", result)
        self.assertEqual(result["task"]["name"], "BACKUP_AND_DELETE")
        self.assertEqual(result["task"]["state"], "INIT") # Still INIT until approved
        self.assertTrue(result["clarification_needed"])
        # 新しいメッセージ形式をチェック
        self.assertIn("複合タスク「BACKUP_AND_DELETE」", result["task"]["clarification_message"])
        self.assertIn("実行してよろしいですか", result["task"]["clarification_message"])

    def test_compound_task_subtask_approval_request_critical_action(self):
        # 1. Setup a compound task in progress, with FILE_DELETE as the next subtask
        # Ensure that test definitions are clean for this test
        self.patcher_load_defs.stop() # Stop the original patcher
        # Re-initialize TaskManager with a specific set of definitions for this test
        specific_mock_defs = {
            "FILE_COPY": {
                "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                "required_entities": ["source_filename", "destination_filename"],
                "transitions": {"INIT": [{"condition": {"type": "all_of", "predicates": [{"type": "entity_exists", "key": "source_filename"}, {"type": "entity_exists", "key": "destination_filename"}]}, "next_state": "READY_FOR_EXECUTION"}]}
            },
            "FILE_DELETE": {
                "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
                "required_entities": ["filename"],
                "transitions": {"INIT": [{"condition": {"type": "entity_exists", "key": "filename"}, "next_state": "READY_FOR_EXECUTION"}]}
            },
            "BACKUP_AND_DELETE": {
                "type": "COMPOUND_TASK",
                "subtasks": [
                    {"name": "FILE_COPY", "parameter_mapping": {"source_filename": "source_filename", "destination_filename": "destination_filename"}},
                    {"name": "FILE_DELETE", "parameter_mapping": {"filename": "source_filename"}}
                ],
                "required_entities": ["source_filename", "destination_filename"],
                "clarification_messages": {"source_filename": "バックアップ元を教えて", "destination_filename": "バックアップ先を教えて"}
            }
        }
        self.tm = TaskManager(action_executor=self.mock_action_executor, task_definitions_path="ignored_path.json")
        self.tm.task_definitions = specific_mock_defs # Directly set task definitions
        self.tm.CRITICAL_INTENTS = ["FILE_DELETE", "CMD_RUN"] # Ensure CRITICAL_INTENTS is set

        # Manually create an in-progress compound task context where FILE_DELETE is next and ready
        in_progress_task = {
            "id": "compound_subtask_approval_session",
            "name": "BACKUP_AND_DELETE",
            "type": "COMPOUND_TASK",
            "state": "IN_PROGRESS",
            "parameters": {
                "source_filename": {"value": "orig_to_delete.txt", "confidence": 0.9},
                "destination_filename": {"value": "backup_done.txt", "confidence": 0.9}
            },
            "subtasks": [
                {"name": "FILE_COPY", "state": "COMPLETED", "parameters": {"source_filename": {"value": "orig_to_delete.txt", "confidence": 0.9}, "destination_filename": {"value": "backup_done.txt", "confidence": 0.9}}},
                {"name": "FILE_DELETE", "state": "READY_FOR_EXECUTION", "parameters": {"filename": {"value": "orig_to_delete.txt", "confidence": 0.9}}}
            ],
            "current_subtask_index": 1,
            "clarification_needed": False,
            "clarification_message": None
        }
        self.tm.active_tasks["compound_subtask_approval_session"] = in_progress_task

        context = {
            "session_id": "compound_subtask_approval_session",
            "analysis": {"intent": "BACKUP_AND_DELETE", "entities": {}} # No new input, just re-evaluating task state
        }
        
        result = self.tm.manage_task_state(context)


        self.assertIn("task", result)
        self.assertEqual(result["task"]["name"], "BACKUP_AND_DELETE")
        self.assertEqual(result["task"]["current_subtask_index"], 1)
        self.assertEqual(result["task"]["subtasks"][1]["name"], "FILE_DELETE")
        self.assertEqual(result["task"]["subtasks"][1]["state"], "READY_FOR_EXECUTION")
        
        # Current specification: skip subtask approval if overall task is IN_PROGRESS
        self.assertFalse(result["clarification_needed"])
        self.assertIsNone(result["task"]["subtasks"][1].get("clarification_message"))

    def test_overall_approval_agree(self):
        # 1. Start a compound task, it should request overall approval
        context = {
            "session_id": "overall_approval_agree_session",
            "analysis": {
                "intent": "BACKUP_AND_DELETE",
                "entities": {
                    "source_filename": {"value": "overall_agree.txt", "confidence": 0.9},
                    "destination_filename": {"value": "overall_agree_backup.txt", "confidence": 0.9}
                }
            }
        }
        result = self.tm.manage_task_state(context)
        self.assertTrue(result["clarification_needed"])
        # 新しいメッセージ形式をチェック（overall_approval_agree用）
        self.assertIn("複合タスク「BACKUP_AND_DELETE」", result["task"]["clarification_message"])
        self.assertIn("実行してよろしいですか", result["task"]["clarification_message"])

        # 2. Simulate user agreeing
        agree_context = {
            "session_id": "overall_approval_agree_session",
            "analysis": {
                "intent": "CLARIFICATION_RESPONSE",
                "entities": {"user_response": {"value": "AGREE", "confidence": 0.9}}
            }
        }
        result = self.tm.manage_task_state(agree_context)
        
        # 3. Assert that the task is now in progress and the first subtask is ready
        self.assertFalse(result.get("clarification_needed", True)) # Clarification should be resolved
        self.assertIn("task", result)
        self.assertEqual(result["task"]["name"], "BACKUP_AND_DELETE")
        self.assertEqual(result["task"]["state"], "IN_PROGRESS")
        self.assertEqual(result["task"]["current_subtask_index"], 0)
        self.assertEqual(result["task"]["subtasks"][0]["name"], "FILE_COPY")
        self.assertEqual(result["task"]["subtasks"][0]["state"], "READY_FOR_EXECUTION")

    def test_overall_approval_disagree(self):
        # 1. Start a compound task, it should request overall approval
        context = {
            "session_id": "overall_approval_disagree_session",
            "analysis": {
                "intent": "BACKUP_AND_DELETE",
                "entities": {
                    "source_filename": {"value": "overall_disagree.txt", "confidence": 0.9},
                    "destination_filename": {"value": "overall_disagree_backup.txt", "confidence": 0.9}
                }
            }
        }
        result = self.tm.manage_task_state(context)
        self.assertTrue(result["clarification_needed"])
        # 新しいメッセージ形式をチェック（overall_approval_disagree用）
        self.assertIn("複合タスク「BACKUP_AND_DELETE」", result["task"]["clarification_message"])
        self.assertIn("実行してよろしいですか", result["task"]["clarification_message"])

        # 2. Simulate user disagreeing
        disagree_context = {
            "session_id": "overall_approval_disagree_session",
            "analysis": {
                "intent": "CLARIFICATION_RESPONSE",
                "entities": {"user_response": {"value": "DISAGREE", "confidence": 0.9}}
            }
        }
        result = self.tm.manage_task_state(disagree_context)
        
        # 3. Assert that the task is cancelled
        self.assertIn("task_cancelled", result)
        self.assertTrue(result["task_cancelled"])
        self.assertNotIn("overall_approval_disagree_session", self.tm.active_tasks)

    def test_subtask_approval_agree(self):
        # 1. Manually set up an in-progress compound task where FILE_DELETE is next and ready
        self.patcher_load_defs.stop() # Stop the original patcher
        specific_mock_defs = {
            "FILE_COPY": {"states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"], "required_entities": ["source_filename", "destination_filename"], "transitions": {"INIT": [{"condition": {"type": "all_of", "predicates": [{"type": "entity_exists", "key": "source_filename"}, {"type": "entity_exists", "key": "destination_filename"}]}, "next_state": "READY_FOR_EXECUTION"}]}},
            "FILE_DELETE": {"states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"], "required_entities": ["filename"], "transitions": {"INIT": [{"condition": {"type": "entity_exists", "key": "filename"}, "next_state": "READY_FOR_EXECUTION"}]}},
                        "BACKUP_AND_DELETE": {
                            "type": "COMPOUND_TASK",
                            "subtasks": [
                                {"name": "FILE_COPY", "parameter_mapping": {"source_filename": "source_filename", "destination_filename": "destination_filename"}},
                                {"name": "FILE_DELETE", "parameter_mapping": {"filename": "source_filename"}}
                            ],
                            "required_entities": ["source_filename", "destination_filename"],
                            "templates": {
                                "overall_approval": "複合タスク「BACKUP_AND_DELETE」を開始します。ファイル '{source_filename}' を '{destination_filename}' にバックアップして削除します。よろしいですか？"
                            }
                        },
            "CLARIFICATION_RESPONSE": {"states": ["INIT", "AGREED", "DISAGREED", "COMPLETED"], "required_entities": ["user_response"], "transitions": {"INIT": [{"condition": {"type": "entity_value_is", "key": "user_response", "value": "AGREE" }, "next_state": "AGREED"}, {"condition": {"type": "entity_value_is", "key": "user_response", "value": "DISAGREE" }, "next_state": "DISAGREED"}]}}
        }
        self.tm = TaskManager(action_executor=self.mock_action_executor, task_definitions_path="ignored_path.json")
        self.tm.task_definitions = specific_mock_defs
        self.tm.CRITICAL_INTENTS = ["FILE_DELETE", "CMD_RUN"]

        in_progress_task = {
            "id": "subtask_approval_agree_session",
            "name": "BACKUP_AND_DELETE",
            "type": "COMPOUND_TASK",
            "state": "IN_PROGRESS",
            "parameters": {"source_filename": {"value": "sub_agree.txt", "confidence": 0.9}, "destination_filename": {"value": "sub_agree_backup.txt", "confidence": 0.9}},
            "subtasks": [
                {"name": "FILE_COPY", "state": "COMPLETED", "parameters": {"source_filename": {"value": "sub_agree.txt", "confidence": 0.9}, "destination_filename": {"value": "sub_agree_backup.txt", "confidence": 0.9}}},
                {"name": "FILE_DELETE", "state": "READY_FOR_EXECUTION", "parameters": {"filename": {"value": "sub_agree.txt", "confidence": 0.9}}, "clarification_needed": False, "clarification_message": None}
            ],
            "current_subtask_index": 1,
            "clarification_needed": False, 
            "clarification_message": None
        }
        self.tm.active_tasks["subtask_approval_agree_session"] = in_progress_task

        context = {
            "session_id": "subtask_approval_agree_session",
            "analysis": {"intent": "BACKUP_AND_DELETE", "entities": {}} # Re-evaluating task state
        }
        result = self.tm.manage_task_state(context)
        self.assertFalse(result["clarification_needed"])
        
        # Since no clarification was needed, it should be ready for execution
        self.assertEqual(result["task"]["subtasks"][1]["state"], "READY_FOR_EXECUTION")

        # 2. Re-evaluate task state. Since it's already IN_PROGRESS and subtask is READY, 
        # it should proceed to execution if ActionExecutor was involved, 
        # or remain IN_PROGRESS/READY until execution.
        # In this unit test, we just check if it correctly skips clarification.
        result = self.tm.manage_task_state(context)
        
        self.assertFalse(result.get("clarification_needed", True))
        self.assertEqual(result["task"]["state"], "IN_PROGRESS") # Still in progress until ActionExecutor finishes it
        self.assertEqual(result["task"]["subtasks"][1]["state"], "READY_FOR_EXECUTION")

    def test_subtask_approval_disagree(self):
        # Current specification: subtask approval is skipped if overall task is IN_PROGRESS.
        # This test case is now verifying that the task remains IN_PROGRESS and no clarification is requested.
        self.patcher_load_defs.stop()
        specific_mock_defs = {
            "FILE_COPY": {"states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"], "required_entities": ["source_filename", "destination_filename"], "transitions": {"INIT": [{"condition": {"type": "all_of", "predicates": [{"type": "entity_exists", "key": "source_filename"}, {"type": "entity_exists", "key": "destination_filename"}]}, "next_state": "READY_FOR_EXECUTION"}]}},
            "FILE_DELETE": {"states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"], "required_entities": ["filename"], "transitions": {"INIT": [{"condition": {"type": "entity_exists", "key": "filename"}, "next_state": "READY_FOR_EXECUTION"}]}},
            "BACKUP_AND_DELETE": {
                "type": "COMPOUND_TASK", 
                "subtasks": [
                    {"name": "FILE_COPY", "parameter_mapping": {"source_filename": "source_filename", "destination_filename": "destination_filename"}}, 
                    {"name": "FILE_DELETE", "parameter_mapping": {"filename": "source_filename"}}
                ], 
                "required_entities": ["source_filename", "destination_filename"],
                "templates": {
                    "overall_approval": "複合タスク「BACKUP_AND_DELETE」を開始します。ファイル '{source_filename}' を '{destination_filename}' にバックアップして削除します。よろしいですか？"
                }
            },
            "CLARIFICATION_RESPONSE": {"states": ["INIT", "AGREED", "DISAGREED", "COMPLETED"], "required_entities": ["user_response"], "transitions": {"INIT": [{"condition": {"type": "entity_value_is", "key": "user_response", "value": "AGREE" }, "next_state": "AGREED"}, {"condition": {"type": "entity_value_is", "key": "user_response", "value": "DISAGREE" }, "next_state": "DISAGREED"}]}}
        }
        self.tm = TaskManager(action_executor=self.mock_action_executor, task_definitions_path="ignored_path.json")
        self.tm.task_definitions = specific_mock_defs
        self.tm.CRITICAL_INTENTS = ["FILE_DELETE", "CMD_RUN"]

        in_progress_task = {
            "id": "subtask_approval_disagree_session",
            "name": "BACKUP_AND_DELETE",
            "type": "COMPOUND_TASK",
            "state": "IN_PROGRESS",
            "parameters": {"source_filename": {"value": "sub_disagree.txt", "confidence": 0.9}, "destination_filename": {"value": "sub_disagree_backup.txt", "confidence": 0.9}},
            "subtasks": [
                {"name": "FILE_COPY", "state": "COMPLETED", "parameters": {"source_filename": {"value": "sub_disagree.txt", "confidence": 0.9}, "destination_filename": {"value": "sub_disagree_backup.txt", "confidence": 0.9}}},
                {"name": "FILE_DELETE", "state": "READY_FOR_EXECUTION", "parameters": {"filename": {"value": "sub_disagree.txt", "confidence": 0.9}}, "clarification_needed": False, "clarification_message": None}
            ],
            "current_subtask_index": 1,
            "clarification_needed": False,
            "clarification_message": None
        }
        self.tm.active_tasks["subtask_approval_disagree_session"] = in_progress_task

        context = {
            "session_id": "subtask_approval_disagree_session",
            "analysis": {"intent": "BACKUP_AND_DELETE", "entities": {}} # Re-evaluating task state
        }
        result = self.tm.manage_task_state(context)
        
        # Should skip clarification because parent task is IN_PROGRESS
        self.assertFalse(result.get("clarification_needed", True))
        self.assertEqual(result["task"]["state"], "IN_PROGRESS")

    def test_interruption_and_re_request_approval(self):
        # 1. Start a compound task, it should request overall approval
        context = {
            "session_id": "interruption_session",
            "analysis": {
                "intent": "BACKUP_AND_DELETE",
                "entities": {
                    "source_filename": {"value": "interrupt.txt", "confidence": 0.9},
                    "destination_filename": {"value": "interrupt_backup.txt", "confidence": 0.9}
                }
            }
        }
        result = self.tm.manage_task_state(context)
        self.assertTrue(result["clarification_needed"])
        # 新しいメッセージ形式をチェック（interruption用）
        self.assertIn("複合タスク「BACKUP_AND_DELETE」", result["task"]["clarification_message"])
        self.assertIn("実行してよろしいですか", result["task"]["clarification_message"])
        self.assertTrue(self.tm.active_tasks["interruption_session"]["clarification_needed"])

        # 2. Simulate user asking a conversational question (interrupting)
        interruption_context = {
            "session_id": "interruption_session",
            "analysis": {
                "intent": "TIME", # Conversational intent
                "entities": {}
            }
        }
        result = self.tm.manage_task_state(interruption_context)

        # 3. Assert that clarification is still needed for the task, and task_interruption flag is set
        self.assertTrue(result["clarification_needed"])
        self.assertTrue(result["task_interruption"])
        # 新しいメッセージ形式をチェック（interruption後）
        self.assertIn("複合タスク「BACKUP_AND_DELETE」", result["task"]["clarification_message"])
        self.assertIn("実行してよろしいですか", result["task"]["clarification_message"])
        self.assertEqual(result["analysis"]["intent"], "TIME") # Original conversational intent is preserved for ResponseGenerator
        self.assertTrue(self.tm.active_tasks["interruption_session"]["clarification_needed"])

        # 4. Simulate user agreeing after the interruption
        agree_context = {
            "session_id": "interruption_session",
            "analysis": {
                "intent": "CLARIFICATION_RESPONSE",
                "entities": {"user_response": {"value": "AGREE", "confidence": 0.9}}
            }
        }
        result = self.tm.manage_task_state(agree_context)

        # 5. Assert that the task is now in progress and the first subtask is ready
        self.assertFalse(result.get("clarification_needed", True)) # Clarification should be resolved
        self.assertIn("task", result)
        self.assertEqual(result["task"]["name"], "BACKUP_AND_DELETE")
        self.assertEqual(result["task"]["state"], "IN_PROGRESS")
        self.assertEqual(result["task"]["current_subtask_index"], 0)
        self.assertEqual(result["task"]["subtasks"][0]["name"], "FILE_COPY")
        self.assertEqual(result["task"]["subtasks"][0]["state"], "READY_FOR_EXECUTION")

    def test_session_management_and_cleanup(self):
        """Test session management functionality"""
        # Test session stats
        stats = self.tm.get_session_stats()
        self.assertIn("active_sessions", stats)
        self.assertIn("max_sessions", stats)
        
        # Create a task
        context = {
            "session_id": "cleanup_test_session",
            "analysis": {
                "intent": "FILE_CREATE",
                "entities": {"filename": {"value": "test.txt", "confidence": 0.9}}
            }
        }
        self.tm.manage_task_state(context)
        
        # Test task state retrieval
        task_state = self.tm.get_task_state("cleanup_test_session")
        self.assertEqual(task_state["status"], "active")
        self.assertEqual(task_state["task_name"], "FILE_CREATE")
        
        # Test force cleanup
        cleaned = self.tm.force_cleanup_session("cleanup_test_session")
        self.assertTrue(cleaned)
        self.assertNotIn("cleanup_test_session", self.tm.active_tasks)
        
        # Test cleanup of non-existent session
        cleaned = self.tm.force_cleanup_session("non_existent")
        self.assertFalse(cleaned)

    def test_memory_usage_stats(self):
        """Test memory usage statistics"""
        # Create some tasks
        for i in range(3):
            context = {
                "session_id": f"memory_test_session_{i}",
                "analysis": {
                    "intent": "FILE_CREATE",
                    "entities": {"filename": {"value": f"test_{i}.txt", "confidence": 0.9}}
                }
            }
            self.tm.manage_task_state(context)
        
        stats = self.tm.get_memory_usage_stats()
        self.assertEqual(stats["active_tasks_count"], 3)
        self.assertIn("estimated_task_memory_bytes", stats)
        self.assertGreater(stats["estimated_task_memory_bytes"], 0)

    def test_task_integrity_validation(self):
        """Test task integrity validation"""
        # Test validation of non-existent task
        result = self.tm.validate_task_integrity("non_existent")
        self.assertTrue(result["valid"])
        self.assertEqual(result["message"], "No active task")
        
        # Create a valid task
        context = {
            "session_id": "integrity_test_session",
            "analysis": {
                "intent": "FILE_CREATE",
                "entities": {"filename": {"value": "test.txt", "confidence": 0.9}}
            }
        }
        self.tm.manage_task_state(context)
        
        # Test validation of valid task
        result = self.tm.validate_task_integrity("integrity_test_session")
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["issues"]), 0)
        
        # Corrupt the task and test validation
        task = self.tm.active_tasks["integrity_test_session"]
        del task["id"]  # Remove required field
        
        result = self.tm.validate_task_integrity("integrity_test_session")
        self.assertFalse(result["valid"])
        self.assertIn("Missing required field: id", result["issues"])

    def test_metrics_integration(self):
        """Test metrics integration"""
        # Enable metrics for this test
        self.tm.config.debug_mode = True
        self.tm.metrics = self.mock_metrics
        self.mock_metrics.cleanup_stale_tasks.return_value = 0
        
        # Create a task (should record start_task)
        context = {
            "session_id": "metrics_test_session",
            "analysis": {
                "intent": "FILE_CREATE",
                "entities": {"filename": {"value": "test.txt", "confidence": 0.9}}
            }
        }
        self.tm.manage_task_state(context)
        
        # Verify metrics were called
        self.mock_metrics.start_task.assert_called_with("metrics_test_session", "FILE_CREATE", "SIMPLE_TASK")
        
        # Reset task (should record completion)
        self.tm.reset_task("metrics_test_session")
        self.mock_metrics.complete_task.assert_called()

    def test_persistence_integration(self):
        """Test persistence integration"""
        # Test that persistence is initialized when enabled
        self.mock_config_manager.get_section.return_value["enable_persistence"] = True
        tm_with_persistence = TaskManager(action_executor=self.mock_action_executor, 
                                          task_definitions_path="ignored_path.json",
                                          config_manager=self.mock_config_manager)
        
        # Verify persistence was initialized
        self.assertIsNotNone(tm_with_persistence.persistence)
        
        # Test that persistence is None when disabled
        self.mock_config_manager.get_section.return_value["enable_persistence"] = False
        tm_without_persistence = TaskManager(action_executor=self.mock_action_executor, 
                                             task_definitions_path="ignored_path.json",
                                             config_manager=self.mock_config_manager)
        
        # Verify persistence was not initialized
        self.assertIsNone(tm_without_persistence.persistence)

    def test_error_handling_improvements(self):
        """Test improved error handling"""
        # Test with invalid configuration (type error during int conversion)
        self.mock_config_manager.get_section.return_value["max_state_age_hours"] = "invalid"
        
        with self.assertRaises(ValueError):
            TaskManager(action_executor=self.mock_action_executor, config_manager=self.mock_config_manager)
        
        # Reset for other tests
        self.mock_config_manager.get_section.return_value["max_state_age_hours"] = 24

    def test_session_limit_enforcement(self):
        """Test session limit enforcement"""
        # Set low session limit
        self.tm.config.max_active_sessions = 2
        
        # Create tasks up to limit
        for i in range(2):
            context = {
                "session_id": f"limit_test_session_{i}",
                "analysis": {
                    "intent": "FILE_CREATE",
                    "entities": {"filename": {"value": f"test_{i}.txt", "confidence": 0.9}}
                }
            }
            result = self.tm.manage_task_state(context)
            # Check that no session limit errors occurred
            if "errors" in result:
                session_limit_errors = [e for e in result["errors"] if "最大セッション数" in e.get("message", "")]
                self.assertEqual(len(session_limit_errors), 0, f"Unexpected session limit error for session {i}")
        
        # Try to create one more (should be rejected)
        context = {
            "session_id": "limit_test_session_overflow",
            "analysis": {
                "intent": "FILE_CREATE",
                "entities": {"filename": {"value": "overflow.txt", "confidence": 0.9}}
            }
        }
        result = self.tm.manage_task_state(context)
        self.assertIn("errors", result)
        self.assertIn("最大セッション数", result["errors"][0]["message"])


if __name__ == '__main__':
    unittest.main()
