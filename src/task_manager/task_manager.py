# -*- coding: utf-8 -*-
# src/task_manager/task_manager.py

import uuid
import json
import os # Added for file operations
import time

from src.utils.confirmation_response import (
    INTENT_AGREE,
    INTENT_CLARIFICATION_RESPONSE,
    INTENT_DISAGREE,
    RESPONSE_APPROVED,
    RESPONSE_REJECTED,
    STATE_AGREED,
    STATE_DISAGREED,
)
from src.utils.action_intents import (
    INTENT_ANALYZE_TEST_FAILURE,
    INTENT_APPLY_CODE_FIX,
    INTENT_CMD_RUN,
    INTENT_EXECUTE_GOAL_DRIVEN_TDD,
    INTENT_FILE_CREATE,
    INTENT_FILE_DELETE,
    INTENT_PROVIDE_CONTENT,
    INTENT_RECOVERY_FROM_TEST_FAILURE,
)
from src.utils.control_intents import (
    INTENT_CANCEL_TASK,
    TASK_INTERRUPTION_INTENTS,
)
from src.utils.dialogue_state import TASK_CLARIFICATION
from src.utils.stdout_guard import debug_print

class TaskManager:
    def __init__(self, action_executor=None, log_manager=None, task_definitions_path=None, config_manager=None):
        """
        Initializes the TaskManager.
        """
        from .metrics import TaskManagerMetrics
        from .state_store import TaskStateStore
        from .approval_messages import ApprovalMessageGenerator
        from .condition_evaluator import ConditionEvaluator
        from .session_manager import SessionManager
        from .approval_workflow import ApprovalWorkflow
        from types import SimpleNamespace

        # 1. Initialize global config manager
        self.config_manager = config_manager

        # 2. Setup internal TaskManager configuration from config_manager or defaults
        tm_config = {}
        if self.config_manager:
            tm_config = self.config_manager.get_section("task_manager")

        # Merge with environment variables for flexibility
        self.config = SimpleNamespace(
            enable_persistence=os.getenv("TASK_PERSISTENCE_ENABLED", str(tm_config.get("enable_persistence", "false"))).lower() == "true",
            persistence_dir=os.getenv("TASK_PERSISTENCE_DIR", tm_config.get("persistence_dir", "cache/tasks")),
            max_state_age_hours=int(os.getenv("TASK_MAX_STATE_AGE_HOURS", str(tm_config.get("max_state_age_hours", 24)))),
            max_active_sessions=int(os.getenv("TASK_MAX_ACTIVE_SESSIONS", str(tm_config.get("max_active_sessions", 100)))),
            session_timeout_minutes=int(os.getenv("TASK_SESSION_TIMEOUT_MINUTES", str(tm_config.get("session_timeout_minutes", 60)))),
            debug_mode=os.getenv("TASK_MANAGER_DEBUG", str(tm_config.get("debug_mode", "false"))).lower() == "true",
            log_state_transitions=os.getenv("TASK_LOG_TRANSITIONS", str(tm_config.get("log_state_transitions", "false"))).lower() == "true",
            max_recovery_attempts=int(tm_config.get("max_recovery_attempts", 3))
        )

        # Critical intents from safety policy if available
        if self.config_manager:
            safety_policy = self.config_manager.get_safety_policy()
            self.CRITICAL_INTENTS = safety_policy.get("destructive_intents", [INTENT_FILE_DELETE, INTENT_CMD_RUN])
        else:
            self.CRITICAL_INTENTS = [INTENT_FILE_DELETE, INTENT_CMD_RUN]

        # 3. Setup paths, preferring config_manager if available
        td_path = task_definitions_path
        if not td_path and config_manager:
            td_path = config_manager.task_definitions_path
        elif not td_path:
            td_path = os.getenv("TASK_DEFINITIONS_PATH", "resources/task_definitions.json")

        self.task_definitions_path = td_path

        self.action_executor = action_executor
        self.log_manager = log_manager
        self.active_tasks = {} # session_id -> current_task_context
        self.session_last_activity = {} # session_id -> timestamp

        # メトリクス収集
        self.metrics = TaskManagerMetrics() if self.config.debug_mode else None

        # 状態永続化
        self.persistence = TaskStateStore(
            enabled=True,
            storage_dir=self.config.persistence_dir,
            max_age_hours=self.config.max_state_age_hours,
            log_manager=self.log_manager
        ) if self.config.enable_persistence else None

        # 承認メッセージジェネレーター
        self.approval_messages = ApprovalMessageGenerator()
        self.approval_workflow = ApprovalWorkflow()

        # 条件評価器
        self.condition_evaluator = ConditionEvaluator()

        # セッション管理
        self.session_manager = SessionManager(self.active_tasks, self.session_last_activity, self.config)

        # Load task definitions
        self.task_definitions = self._load_task_definitions(self.task_definitions_path)
        self.intent_to_recommended_action = {
            INTENT_ANALYZE_TEST_FAILURE: "analyze_test_failure",
            INTENT_EXECUTE_GOAL_DRIVEN_TDD: "execute_goal_driven_tdd",
            INTENT_APPLY_CODE_FIX: "apply_code_fix",
        }

    def _load_task_definitions(self, filepath: str) -> dict:
        """Loads task definitions from a JSON file or returns hardcoded defaults."""
        from tests.fixtures.task_definitions import COMMON_TASK_DEFINITIONS
        default_definitions = COMMON_TASK_DEFINITIONS.copy()

        if not os.path.exists(filepath):
            return default_definitions

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                loaded_definitions = json.load(f)
                return loaded_definitions
        except (FileNotFoundError, PermissionError) as e:
            # ファイルアクセスエラー - ログに記録して継続
            self._log_error(f"Could not access task definitions file {filepath}: {e}")
            return default_definitions
        except json.JSONDecodeError as e:
            # JSON解析エラー - より具体的なエラー情報
            self._log_error(f"Invalid JSON in task definitions file {filepath}: {e}")
            return default_definitions
        except Exception as e:
            # 予期しないエラー - ログに記録して継続
            self._log_error(f"Unexpected error loading task definitions from {filepath}: {e}")
            return default_definitions

    def _log_error(self, message: str):
        """エラーログの出力"""
        if self.log_manager:
            self.log_manager.log_event("task_manager_error", {"message": message}, level="ERROR")
        elif self.config and self.config.debug_mode:
            debug_print(f"[TaskManager ERROR] {message}")

    def _log_debug(self, message: str):
        """デバッグログの出力"""
        if self.log_manager:
            self.log_manager.log_event("task_manager_debug", {"message": message}, level="DEBUG")
        elif self.config and self.config.debug_mode:
            # Fallback if no log_manager but debug_mode is on
            pass

    def _log_state_transition(self, session_id: str, from_state: str, to_state: str, task_name: str):
        """状態遷移ログの出力"""
        if self.log_manager:
            self.log_manager.log_event("task_state_transition", {
                "session_id": session_id,
                "task_name": task_name,
                "from_state": from_state,
                "to_state": to_state
            }, level="INFO")
        elif self.config and self.config.log_state_transitions:
            # Fallback if no log_manager
            pass

        if self.metrics:
            self.metrics.record_state_transition(session_id, from_state, to_state)

    def _evaluate_condition(self, condition: any, context: dict) -> bool:
        """条件評価をConditionEvaluatorに委譲"""
        return self.condition_evaluator.evaluate(condition, context)

    def _get_recommended_action_for_intent(self, intent: str) -> str:
        return self.intent_to_recommended_action.get(intent, "")

    def _apply_recommended_action_metadata(self, task_data: dict, intent: str | None = None):
        if not isinstance(task_data, dict):
            return

        effective_intent = intent or task_data.get("name", "")
        recommended_action = self._get_recommended_action_for_intent(effective_intent)
        if recommended_action:
            task_data["recommended_action"] = recommended_action

    def manage_task_state(self, context: dict) -> dict:
        """
        Manages the state of ongoing tasks or initiates new ones based on intent and entities.
        Args:
            context (dict): The pipeline context object containing analysis, intent, and entities.
        Returns:
            dict: The updated context object, potentially with a 'task' field describing the current task state.
        """
        session_id = context.get("session_id", "default_session")

        # セッション活動の更新
        self._update_session_activity(session_id)

        # セッション数制限のチェック
        if (len(self.active_tasks) >= self.config.max_active_sessions and
            session_id not in self.active_tasks):
            context.setdefault("errors", []).append({
                "module": "task_manager",
                "message": f"最大セッション数({self.config.max_active_sessions})に達しています。"
            })
            return context

        # 定期的なクリーンアップ（10%の確率で実行）
        import random
        if random.random() < 0.1:
            self.cleanup_stale_sessions()

        context.setdefault("errors", []) # Ensure errors list is always present
        context.setdefault("clarification_needed", False) # Ensure clarification_needed exists and is false by default

        intent = context["analysis"].get("intent")
        entities = context["analysis"].get("entities", {})

        self._log_debug(f"Managing task state for session {session_id}, intent: {intent}")

        current_task = self.active_tasks.get(session_id)
        if current_task:
            awaiting_entity = current_task.get("awaiting_entity")
            if (
                awaiting_entity in {"source_filename", "destination_filename", "project_path"}
                and awaiting_entity not in entities
                and entities.get("filename")
            ):
                entities[awaiting_entity] = entities.pop("filename")

        # If PROVIDE_CONTENT arrives without an active task but includes a filename,
        # treat it as FILE_CREATE to avoid orphan content intents.
        if not current_task and intent == INTENT_PROVIDE_CONTENT:
            fn_entity = entities.get("filename")
            fn_val = fn_entity.get("value") if isinstance(fn_entity, dict) else fn_entity
            if fn_val:
                intent = INTENT_FILE_CREATE
                context["analysis"]["intent"] = INTENT_FILE_CREATE

        # --- NEW: Propagate entities from current turn to task parameters ---
        if current_task:
            self._apply_recommended_action_metadata(current_task)
            for entity_key, entity_data in entities.items():
                val = None
                conf = 1.0
                if isinstance(entity_data, dict):
                    val = entity_data.get("value")
                    conf = entity_data.get("confidence", 1.0)
                else:
                    val = entity_data

                if val:
                    # Update if not exists or if current is empty or if new is higher confidence
                    current_val = current_task["parameters"].get(entity_key)
                    if not current_val or conf >= current_task["parameters"].get(f"{entity_key}_confidence", 0):
                        current_task["parameters"][entity_key] = val
                        current_task["parameters"][f"{entity_key}_confidence"] = conf
        # -------------------------------------------------------------------


        # --- NEW: Prioritize CLARIFICATION_RESPONSE (AGREE/DISAGREE) ---
        if intent in [INTENT_CLARIFICATION_RESPONSE, INTENT_AGREE, INTENT_DISAGREE]:
            self._log_debug(f"Processing {intent} for session {session_id}")
            active_task = self.active_tasks.get(session_id)
            if active_task and active_task.get("clarification_needed"):
                self._log_debug(f"Active task found with clarification needed: {active_task['name']}")

                # Check for user_response entity (from vector fallback) or directly use intent
                user_response_val = self.approval_workflow.response_value(
                    intent,
                    entities,
                    INTENT_AGREE,
                    INTENT_DISAGREE,
                    RESPONSE_APPROVED,
                    RESPONSE_REJECTED,
                )

                # Temporarily store for evaluation
                active_task["parameters"]["user_response"] = user_response_val

                clarification_task_def = self.task_definitions.get(INTENT_CLARIFICATION_RESPONSE)
                if clarification_task_def:
                    clarification_eval_context = {
                        "analysis": {"entities": {"user_response": {"value": user_response_val}}},
                        "task": active_task
                    }
                    transitions = clarification_task_def.get("transitions", {}).get("INIT", [])

                    for transition in transitions:
                        if self._evaluate_condition(transition["condition"], clarification_eval_context):
                            if transition["next_state"] == STATE_AGREED:
                                active_task["clarification_needed"] = False
                                active_task["clarification_message"] = None
                                active_task["clarification_type"] = None
                                active_task.pop("awaiting_entity", None)
                                self.approval_workflow.record_decision(
                                    active_task,
                                    self.approval_workflow.APPROVED,
                                )

                                if active_task.get("type") == "COMPOUND_TASK" and active_task.get("state") == "INIT":
                                    active_task["state"] = "IN_PROGRESS"

                                active_task["parameters"].pop("user_response", None)
                                # Reset intent to trigger re-evaluation of the now-approved task
                                context["analysis"]["intent"] = active_task["name"]
                                context["clarification_needed"] = False
                                return self.manage_task_state(context)

                            elif transition["next_state"] == STATE_DISAGREED:
                                self.reset_task(session_id)
                                context["task_cancelled"] = True
                                context["clarification_needed"] = False
                                context["dialogue_state"] = None
                                context["response"] = {"text": "タスクがキャンセルされました。"}
                                return context
        # -------------------------------------------------------------

        conversational_intents = TASK_INTERRUPTION_INTENTS + (INTENT_AGREE, INTENT_DISAGREE)

        # 永続化からの状態復旧
        if not current_task and self.persistence:
            restored_task = self.persistence.load_task_state(session_id)
            if restored_task:
                self.active_tasks[session_id] = restored_task
                current_task = restored_task
                self._log_debug(f"Restored task state for session {session_id}")

        # Handle CANCEL_TASK explicitly
        if intent == INTENT_CANCEL_TASK:
            if session_id in self.active_tasks:
                del self.active_tasks[session_id]
                context["task_cancelled"] = True
            else:
                context["task_cancelled_no_active"] = True
            self._update_clarification_status(context)
            return context

        # --- NEW: Early Interruption Check ---
        # If there's an active task and the current input is a conversational intent
        # with no entities, treat it as an interruption.
        if current_task and intent in conversational_intents and not entities:
            # We need the active task's clarification message if it's awaiting input
            active_task_context_for_interruption = None
            if current_task.get("type") == "COMPOUND_TASK":
                # Check if parent task needs overall approval first
                if current_task.get("state") == "INIT" and current_task.get("clarification_needed"):
                    active_task_context_for_interruption = current_task
                else:
                    sub_task_index = current_task.get("current_subtask_index", 0)
                    if sub_task_index < len(current_task.get("subtasks", [])):
                        active_task_context_for_interruption = current_task["subtasks"][sub_task_index]
                    else: # Parent compound task itself needs entities
                        parent_missing_entities = [
                            req_ent for req_ent in self.task_definitions.get(current_task["name"], {}).get("required_entities", [])
                            if not current_task["parameters"].get(req_ent)
                        ]
                        if parent_missing_entities and current_task["state"] == "INIT":
                            active_task_context_for_interruption = current_task
            else: # Simple Task
                active_task_context_for_interruption = current_task

            if active_task_context_for_interruption and active_task_context_for_interruption.get("clarification_needed"):
                context["task"] = current_task # Keep parent task in context
                context["task_interruption"] = True
                context["analysis"]["intent"] = intent # Revert intent to conversational for Pipeline

                # メトリクス記録
                if self.metrics:
                    self.metrics.record_interruption(session_id, "CONVERSATIONAL_DURING_CLARIFICATION")

                # NOTE: We NO LONGER set context["response"] here.
                # Let ResponseGenerator handle the conversational response first.
                # The task state is preserved, and clarification_needed remains true.

                # Set clarification_needed for early return
                self._update_clarification_status(context)
                return context

        # --- END NEW: Early Interruption Check ---

        # Handle CLARIFICATION_RESPONSE intent (including AGREE/DISAGREE)
        if intent in [INTENT_CLARIFICATION_RESPONSE, INTENT_AGREE, INTENT_DISAGREE]:
            self._log_debug(f"Processing {intent} for session {session_id}")
            active_task = self.active_tasks.get(session_id)
            if active_task and active_task.get("clarification_needed"):
                self._log_debug(f"Active task found with clarification needed: {active_task['name']}")
                user_response_entity = entities.get("user_response")
                if user_response_entity and user_response_entity.get("value"):
                    self._log_debug(f"User response entity found: {user_response_entity}")
                    # Temporarily store the user's response in the active task's context for evaluation
                    active_task["parameters"]["user_response"] = user_response_entity

                    # Evaluate the user's response against the clarification_response task definition
                    clarification_task_def = self.task_definitions.get(INTENT_CLARIFICATION_RESPONSE)
                    if clarification_task_def:
                        self._log_debug("Found CLARIFICATION_RESPONSE task definition")
                        # Create a temporary context for evaluating clarification response transitions
                        clarification_eval_context = {
                            "analysis": {"entities": entities},  # Use current turn entities which include user_response
                            "task": active_task
                        }
                        transitions = clarification_task_def.get("transitions", {}).get("INIT", [])

                        for transition in transitions:
                            if self._evaluate_condition(transition["condition"], clarification_eval_context):
                                self._log_debug(f"Transition condition met: {transition['next_state']}")
                                if transition["next_state"] == STATE_AGREED:
                                    self._log_debug("User agreed to task execution")
                                    # User agreed, clear clarification needed flags and re-evaluate the original task
                                    active_task["clarification_needed"] = False
                                    active_task["clarification_message"] = None

                                    # 承認履歴の記録
                                    self.approval_workflow.record_decision(
                                        active_task,
                                        self.approval_workflow.APPROVED,
                                    )

                                    # For compound tasks, set state to IN_PROGRESS after overall approval
                                    if active_task.get("type") == "COMPOUND_TASK" and active_task.get("state") == "INIT":
                                        active_task["state"] = "IN_PROGRESS"

                                    # For compound tasks, also clear subtask clarification flags
                                    if active_task.get("type") == "COMPOUND_TASK":
                                        current_subtask_index = active_task.get("current_subtask_index", 0)
                                        if current_subtask_index < len(active_task.get("subtasks", [])):
                                            current_subtask = active_task["subtasks"][current_subtask_index]
                                            current_subtask["clarification_needed"] = False
                                            current_subtask["clarification_message"] = None
                                            # Also clear any other subtasks that might have clarification flags
                                            for subtask in active_task["subtasks"]:
                                                if subtask.get("clarification_needed"):
                                                    subtask["clarification_needed"] = False
                                                    subtask["clarification_message"] = None

                                    # Remove user_response parameter from active task
                                    active_task["parameters"].pop("user_response", None)
                                    # Recursively call manage_task_state to re-process the active task, now that it's agreed

                                    # 複合タスクの場合は、現在のサブタスクのインテントを設定
                                    if active_task.get("type") == "COMPOUND_TASK":
                                        current_subtask_index = active_task.get("current_subtask_index", 0)
                                        if current_subtask_index < len(active_task["subtasks"]):
                                            current_subtask = active_task["subtasks"][current_subtask_index]
                                            context["analysis"]["intent"] = current_subtask["name"] # サブタスクのインテントを設定
                                        else:
                                            context["analysis"]["intent"] = active_task["name"] # 親タスクのインテント
                                    else:
                                        context["analysis"]["intent"] = active_task["name"] # Set intent to active task name for re-evaluation
                                    # Ensure entities are correct for re-evaluation, if any were part of the agreement
                                    if active_task.get("type") == "COMPOUND_TASK":
                                        # 複合タスクの場合は、親タスクのパラメータを使用
                                        context["analysis"]["entities"] = active_task.get("parameters", {})
                                    else:
                                        # 単純タスクの場合は、タスクのパラメータを使用
                                        context["analysis"]["entities"] = active_task["parameters"]

                                    # Remove the clarification_needed from the input context for this recursive call
                                    context["clarification_needed"] = False

                                    # If action_result is present, process it after approval
                                    if context.get("action_result"):
                                        # Process action result first, then return directly
                                        return self.update_task_after_execution(context)

                                    return self.manage_task_state(context) # Recursive call

                                elif transition["next_state"] == STATE_DISAGREED:
                                    # User disagreed, cancel the active task
                                    # 拒否履歴の記録
                                    self.approval_workflow.record_decision(
                                        active_task,
                                        self.approval_workflow.REJECTED,
                                    )

                                    self.reset_task(session_id)
                                    context["task_cancelled"] = True
                                    context["clarification_needed"] = False # Clarification handled, no longer needed
                                    context["dialogue_state"] = None
                                    context.setdefault("response", {})
                                    context["response"]["text"] = "タスクがキャンセルされました。"
                                    self._update_clarification_status(context)
                                    return context
            # If CLARIFICATION_RESPONSE intent but no active task or no clear response, fall through
            # to regular processing, which might lead to clarification about the clarification.

        # Determine the effective intent for task management
        effective_intent = intent # Start with the current turn's intent

        # If there's an active task, prioritize its name as effective_intent
        if current_task:
            effective_intent = current_task["name"]

            # Logic to allow switching to a new non-conversational task if current task is in final state
            if intent not in conversational_intents and intent != current_task["name"] and self.task_definitions.get(intent):
                if not entities and current_task["state"] in ["READY_FOR_EXECUTION", "COMPLETED", "FAILED"]:
                    effective_intent = intent # Allow switching
                    current_task = None # Signal to initiate new task below
                # Else: (if there are entities, or current task is not in final state), effective_intent remains current_task["name"]

        # Now, look up the task definition using the finalized effective_intent
        task_definition = self.task_definitions.get(effective_intent)

        # Handle unknown intent scenario when no active task or when trying to switch to an unknown task
        if not task_definition: # If the effective_intent does not have a definition
            if effective_intent in conversational_intents:
                # If conversational intent, regardless of active task status,
                # we want to let the pipeline handle it as a conversation.
                # However, if there is an active task, we should simply NOT update the task state.
                # This effectively "pauses" the task for one turn.
                if current_task:
                    # Check if the input contains entities relevant to the task (or any entities).
                    # If it has entities (e.g., "test.txt" -> filename), it's likely a slot-filling answer
                    # that was misclassified as GENERAL/conversational.
                    has_new_entities = bool(context["analysis"].get("entities"))

                    if not has_new_entities:
                        # Treat as simple interruption: Return context with task info but without processing this input
                        context["task"] = current_task
                        context["task_interruption"] = True # Signal pipeline to interpret as conversation

                        # メトリクス記録
                        if self.metrics:
                            self.metrics.record_interruption(session_id, "CONVERSATIONAL_NO_ENTITIES")

                        # Set clarification_needed based on current task state
                        if current_task.get("clarification_needed"):
                            context["clarification_needed"] = True
                        self._update_clarification_status(context)
                        return context
                    # Else: Proceed to update task with entities
                    # We need to ensure task_definition is set to the current task's definition
                    # so that transitions can be evaluated.
                    task_definition = self.task_definitions.get(current_task["name"])
                else:
                    self._update_clarification_status(context)
                    return context
            elif not current_task or current_task["state"] in ["COMPLETED", "FAILED"]:
                # If it's not a conversational intent and no task definition, then it's an error.
                context.setdefault("errors", []).append({
                    "module": "task_manager",
                    "message": f"タスク定義 '{effective_intent}' が見つかりません。"
                })
                self._update_clarification_status(context)
                return context # Return early with error
            # If there is an active task and the new intent is unknown, let clarification handle it
            # This branch implies that the user might be trying to do something outside the current task's scope
            # and ClarificationManager should then ask. We don't want to prematurely reset the current_task here.

        if not current_task and task_definition:
            current_task = self._initiate_task(
                session_id,
                context,
                effective_intent,
                task_definition,
                entities,
            )

        if current_task:
            context["task"] = current_task # Set it early so _evaluate_condition can see it
            task_name = current_task["name"]
            self._apply_recommended_action_metadata(current_task, task_name)
            task_type = current_task.get("type", "SIMPLE_TASK") # Default to SIMPLE_TASK for old definitions
            task_def = self.task_definitions.get(task_name)

            if not task_def:
                context["errors"].append({
                    "module": "task_manager",
                    "message": f"タスク定義 '{task_name}' が見つかりません。"
                })
                self._update_clarification_status(context)
                return context

            if task_type == "COMPOUND_TASK":
                return self._manage_compound_task(session_id, context, current_task, entities)

            self._manage_simple_task(session_id, context, current_task, task_def, entities)

        if current_task and current_task.get("state") == "READY_FOR_EXECUTION" and not current_task.get("clarification_needed"):
            context["analysis"]["intent"] = current_task.get("name")

        self._update_clarification_status(context)
        return context

    def _initiate_task(self, session_id, context, intent, task_definition, entities):
        """Create, register, and persist one task from a validated definition."""
        is_compound = task_definition.get("type") == "COMPOUND_TASK"
        if is_compound:
            task = {
                "id": str(uuid.uuid4()),
                "name": intent,
                "type": "COMPOUND_TASK",
                "state": "INIT",
                "parameters": {},
                "subtasks": [
                    {"name": definition["name"], "state": "PENDING", "parameters": {}}
                    for definition in task_definition.get("subtasks", [])
                ],
                "current_subtask_index": 0,
                "history": [],
                "recovery_attempts": 0,
                "clarification_needed": task_definition.get("require_overall_approval", True),
                "clarification_message": None,
                "clarification_type": "APPROVAL" if task_definition.get("require_overall_approval", True) else None,
            }
        else:
            task = {
                "id": str(uuid.uuid4()),
                "name": intent,
                "type": "SIMPLE_TASK",
                "state": "INIT",
                "parameters": {},
                "history": [],
                "clarification_needed": False,
                "clarification_message": None,
                "clarification_type": None,
            }

        self._apply_recommended_action_metadata(task, intent)
        for entity_key, entity_data in entities.items():
            if entity_data.get("value"):
                task["parameters"][entity_key] = entity_data

        self.active_tasks[session_id] = task
        if self.metrics:
            self.metrics.start_task(session_id, intent, task_definition.get("type", "SIMPLE_TASK"))
        if self.persistence:
            self.persistence.save_task_state(session_id, task)
        context["analysis"]["task_initiated"] = True

        if is_compound and task_definition.get("require_overall_approval", True):
            context["clarification_needed"] = True
            approval_message = self.approval_messages.generate_overall_approval_message(
                intent,
                task["parameters"],
                self.task_definitions,
            )
            task["clarification_message"] = approval_message
            task["clarification_type"] = "APPROVAL"
            context["response"] = {"text": approval_message}
            if self.log_manager:
                self.log_manager.log_event("clarification_needed", {"message": approval_message}, level="INFO")
        self._log_debug(f"Created new task: {intent} for session {session_id}")
        return task

    def _manage_compound_task(self, session_id, context, current_task, entities):
        """Advance the active subtask, including its approval and slot-filling flow."""
        if current_task.get("state") == "INIT" and current_task.get("clarification_needed"):
            self._update_clarification_status(context)
            return context

        subtask_index = current_task.get("current_subtask_index", 0)
        if subtask_index >= len(current_task.get("subtasks", [])):
            self._update_clarification_status(context)
            return context

        subtask = current_task["subtasks"][subtask_index]
        self._apply_recommended_action_metadata(subtask, subtask.get("name"))
        subtask_definition = self.task_definitions.get(subtask["name"])
        if not subtask_definition:
            context["errors"].append({
                "module": "task_manager",
                "message": f"複合タスク '{current_task['name']}' のサブタスク '{subtask['name']}' の定義が見つかりません。",
            })
            self.reset_task(session_id)
            self._update_clarification_status(context)
            return context

        self._advance_pending_subtask(session_id, current_task, subtask, subtask_definition, entities, subtask_index)
        self._request_subtask_approval_if_needed(session_id, context, current_task, subtask)
        self._request_missing_subtask_entity(context, current_task, subtask, subtask_definition)

        current_task["subtasks"][subtask_index] = subtask
        context["task"] = current_task
        if subtask.get("clarification_needed"):
            context["clarification_needed"] = True
        return context

    def _advance_pending_subtask(self, session_id, parent_task, subtask, subtask_definition, entities, subtask_index):
        if subtask.get("state") not in ["PENDING", "INIT"]:
            return

        subtask.setdefault("parameters", {})
        parent_definition = self.task_definitions.get(parent_task["name"], {})
        subtask_specification = parent_definition.get("subtasks", [])[subtask_index]
        for subtask_parameter, parent_parameter in subtask_specification.get("parameter_mapping", {}).items():
            if parent_parameter in parent_task["parameters"]:
                subtask["parameters"][subtask_parameter] = parent_task["parameters"][parent_parameter]
        for entity_key, entity_data in entities.items():
            if entity_data.get("value"):
                subtask["parameters"][entity_key] = entity_data

        current_state = subtask.get("state", "INIT")
        if current_state == "PENDING":
            current_state = "INIT"
        evaluation_context = {"analysis": {"entities": subtask["parameters"]}, "task": subtask}
        for transition in subtask_definition.get("transitions", {}).get(current_state, []):
            if self._evaluate_condition(transition["condition"], evaluation_context):
                old_state = subtask.get("state", "INIT")
                subtask["state"] = transition["next_state"]
                subtask["clarification_needed"] = False
                subtask["clarification_message"] = None
                subtask["clarification_type"] = None
                self._log_state_transition(
                    session_id,
                    old_state,
                    subtask["state"],
                    f"{parent_task['name']}.{subtask['name']}",
                )
                if self.persistence:
                    self.persistence.save_task_state(session_id, parent_task)
                return

    def _request_subtask_approval_if_needed(self, session_id, context, parent_task, subtask):
        needs_approval = (
            subtask["state"] == "READY_FOR_EXECUTION"
            and subtask["name"] in self.CRITICAL_INTENTS
            and not subtask.get("clarification_needed", False)
            and parent_task.get("state") != "IN_PROGRESS"
        )
        if not needs_approval:
            return

        subtask["clarification_needed"] = True
        subtask["clarification_message"] = self.approval_messages.generate_critical_subtask_message(
            parent_task.get("name", "不明なタスク"),
            subtask.get("name", "不明なサブタスク"),
            subtask.get("parameters", {}),
            self.task_definitions,
        )
        subtask["clarification_type"] = "APPROVAL"
        parent_task["clarification_type"] = "APPROVAL"
        context["clarification_needed"] = True
        if self.metrics:
            self.metrics.record_approval_request(session_id, "CRITICAL_SUBTASK")

    @staticmethod
    def _missing_task_entities(task, task_definition):
        return [
            required
            for required in task_definition.get("required_entities", [])
            if required not in task["parameters"] or not task["parameters"].get(required)
        ]

    def _request_missing_subtask_entity(self, context, parent_task, subtask, subtask_definition):
        if context.get("clarification_needed") or subtask["state"] == "READY_FOR_EXECUTION":
            return
        missing_entities = self._missing_task_entities(subtask, subtask_definition)
        if not missing_entities:
            subtask["clarification_needed"] = False
            subtask["clarification_message"] = None
            subtask["clarification_type"] = None
            subtask.pop("awaiting_entity", None)
            return

        missing_entity = missing_entities[0]
        message = subtask_definition.get("clarification_messages", {}).get(
            missing_entity,
            f"複合タスク「{parent_task['name']}」のサブタスク「{subtask['name']}」で、情報「{missing_entity}」が必要です。",
        )
        subtask["clarification_needed"] = True
        subtask["clarification_message"] = message
        subtask["clarification_type"] = "MISSING_ENTITY"
        subtask["awaiting_entity"] = missing_entity
        context["clarification_needed"] = True
        context.setdefault("response", {})["text"] = message

    def _manage_simple_task(self, session_id, context, current_task, task_definition, entities):
        """Merge entities, advance one state transition, then request a missing slot."""
        for entity_key, entity_data in entities.items():
            if isinstance(entity_data, dict) and entity_data.get("value"):
                current_task["parameters"][entity_key] = entity_data
            elif isinstance(entity_data, str):
                current_task["parameters"][entity_key] = {"value": entity_data, "confidence": 1.0}

        for transition in task_definition.get("transitions", {}).get(current_task["state"], []):
            if self._evaluate_condition(transition["condition"], context):
                old_state = current_task.get("state", "INIT")
                current_task["state"] = transition["next_state"]
                current_task["clarification_needed"] = False
                current_task["clarification_message"] = None
                current_task["clarification_type"] = None
                current_task.pop("awaiting_entity", None)
                self._log_state_transition(session_id, old_state, current_task["state"], current_task["name"])
                if self.persistence:
                    self.persistence.save_task_state(session_id, current_task)
                break

        if current_task["state"] != "READY_FOR_EXECUTION":
            self._request_missing_simple_task_entity(session_id, context, current_task, task_definition)
        context["task"] = current_task

    def _request_missing_simple_task_entity(self, session_id, context, current_task, task_definition):
        missing_entities = []
        for required in task_definition.get("required_entities", []):
            value = current_task["parameters"].get(required)
            if not value or (isinstance(value, dict) and not value.get("value")):
                missing_entities.append(required)
        if not missing_entities:
            return

        missing_entity = missing_entities[0]
        message = task_definition.get("clarification_messages", {}).get(
            missing_entity,
            f"タスク「{current_task['name']}」で、情報「{missing_entity}」が必要です。",
        )
        current_task["clarification_needed"] = True
        current_task["clarification_message"] = message
        current_task["clarification_type"] = "MISSING_ENTITY"
        current_task["awaiting_entity"] = missing_entity
        context["clarification_needed"] = True
        if self.log_manager:
            self.log_manager.log_event("clarification_needed", {"message": message}, level="INFO")
        context["analysis"]["awaiting_entity"] = missing_entity
        if self.metrics:
            self.metrics.record_approval_request(session_id, "MISSING_ENTITY")
        context.setdefault("response", {})["text"] = message

    def update_task_after_execution(self, context: dict) -> dict:
        """
        Updates the task state after an action has been executed.
        Sets the task state to COMPLETED or FAILED based on action_result.
        Handles both simple and compound tasks.
        """
        session_id = context.get("session_id")

        if not session_id:
            return context

        current_task = self.active_tasks.get(session_id)
        action_result = context.get("action_result", {})

        if current_task and action_result:
            task_type = current_task.get("type", "SIMPLE_TASK") # Default to SIMPLE_TASK

            if task_type == "COMPOUND_TASK":
                sub_task_index = current_task.get("current_subtask_index", 0)
                if sub_task_index < len(current_task["subtasks"]):
                    active_subtask = current_task["subtasks"][sub_task_index]

                    if action_result.get("status") == "success":
                        active_subtask["state"] = "COMPLETED"
                        # Move to next subtask
                        current_task["current_subtask_index"] += 1

                        # Check if all subtasks are completed
                        if current_task["current_subtask_index"] >= len(current_task["subtasks"]):
                            current_task["state"] = "COMPLETED"
                        else:
                            current_task["state"] = "IN_PROGRESS" # Ensure parent state is IN_PROGRESS if not all subtasks done
                    else: # Subtask failed
                        active_subtask["state"] = "FAILED"
                        current_task["state"] = "FAILED" # Parent task fails if any subtask fails
                else:
                    # Should not happen if current_subtask_index is managed correctly
                    # Log error would be handled by pipeline_core
                    current_task["state"] = "FAILED"

            else: # SIMPLE_TASK
                if action_result.get("status") == "success":
                    current_task["state"] = "COMPLETED"
                else:
                    current_task["state"] = "FAILED"

            # Update context's task field with the latest state
            context["task"] = current_task

            # If the main task (simple or compound) is completed or failed, remove it from active tasks
            if current_task["state"] in ["COMPLETED", "FAILED"]:
                self.reset_task(session_id)

        return context

    def reset_task(self, session_id: str):
        """Resets the active active task for a given session."""
        if session_id in self.active_tasks:
            task = self.active_tasks[session_id]
            task_name = task.get("name", "unknown")

            self._log_debug(f"Resetting task {task_name} for session {session_id}")

            # メトリクス記録
            if self.metrics:
                final_state = task.get("state", "UNKNOWN")
                self.metrics.complete_task(session_id, final_state)

            # 永続化状態の削除
            if self.persistence:
                self.persistence.delete_task_state(session_id)

            del self.active_tasks[session_id]

        if session_id in self.session_last_activity:
            del self.session_last_activity[session_id]

    def _update_session_activity(self, session_id: str):
        """セッションの最終活動時刻を更新"""
        self.session_manager.update_activity(session_id)

    def cleanup_stale_sessions(self):
        """古いセッションのクリーンアップ"""
        import time
        current_time = time.time()
        timeout_seconds = self.config.session_timeout_minutes * 60

        stale_sessions = []
        for session_id, last_activity in self.session_last_activity.items():
            if current_time - last_activity > timeout_seconds:
                stale_sessions.append(session_id)

        for session_id in stale_sessions:
            task = self.active_tasks.get(session_id)
            if task and task.get("clarification_needed"):
                self._log_debug(f"Cleaning up stale session with pending approval: {session_id}")
                # 承認待ちタスクの特別処理
                if self.metrics:
                    self.metrics.complete_task(session_id, "APPROVAL_TIMEOUT")
            else:
                self._log_debug(f"Cleaning up stale session: {session_id}")
            self.reset_task(session_id)

        # メトリクスのクリーンアップ
        if self.metrics:
            cleaned_count = self.metrics.cleanup_stale_tasks(
                max_age_hours=self.config.max_state_age_hours
            )
            if cleaned_count > 0:
                self._log_debug(f"Cleaned up {cleaned_count} stale task metrics")

        # 永続化ファイルのクリーンアップ
        if self.persistence:
            self.persistence.cleanup_old_states()

        return len(stale_sessions)

    def get_session_stats(self) -> dict:
        """セッション統計の取得"""
        stats = self.session_manager.get_stats()

        if self.metrics:
            stats.update(self.metrics.get_summary_stats())

        return stats

    def get_session_id(self, context: dict) -> str:
        """contextからsession_idを抽出、またはデフォルトを返す"""
        return self.session_manager.get_session_id(context)

    def is_task_active(self, session_id: str) -> bool:
        """セッションにアクティブなタスクがあるかチェック"""
        return self.session_manager.is_task_active(session_id)

    def _update_clarification_status(self, context: dict):
        """contextのトップレベルのclarification_neededをタスクの状態と同期"""
        session_id = context.get("session_id", "default_session")
        current_task = self.active_tasks.get(session_id)
        if current_task:
            context["clarification_needed"] = current_task.get("clarification_needed", False)
            if current_task.get("clarification_needed"):
                context["dialogue_state"] = TASK_CLARIFICATION
            elif context.get("dialogue_state") == TASK_CLARIFICATION:
                context["dialogue_state"] = None

    def get_task_state(self, session_id: str) -> dict:
        """タスクの現在状態を取得"""
        return self.session_manager.get_task_state(session_id)

    def force_cleanup_session(self, session_id: str) -> bool:
        """
        指定セッションを強制的にクリーンアップ

        Args:
            session_id: クリーンアップするセッションID

        Returns:
            bool: クリーンアップが実行されたかどうか
        """
        if session_id in self.active_tasks:
            self._log_debug(f"Force cleaning up session: {session_id}")

            # メトリクス記録
            if self.metrics:
                self.metrics.complete_task(session_id, "FORCE_CLEANUP")

            # 永続化状態の削除
            if self.persistence:
                self.persistence.delete_task_state(session_id)

            del self.active_tasks[session_id]

            if session_id in self.session_last_activity:
                del self.session_last_activity[session_id]

            return True

        return False

    def create_recovery_task(self, session_id: str, context: dict) -> dict:
        """
        エラーが発生したコンテキストに基づいて、回復用の複合タスクを生成・登録する。
        """
        error_result = context.get("action_result", {})
        if not error_result or error_result.get("status") != "error":
            return context

        # 既存タスクの試行回数を引き継ぐ
        attempts = 0
        if session_id in self.active_tasks:
            attempts = self.active_tasks[session_id].get("recovery_attempts", 0)

        self._log_debug(f"Creating recovery task for session {session_id}, attempt {attempts + 1}")

        # 回復タスクの意図を設定
        recovery_intent = INTENT_RECOVERY_FROM_TEST_FAILURE # 現時点ではテスト失敗に特化

        # 既存のタスクがあればリセット
        self.reset_task(session_id)

        # 必要なエンティティをコンテキストから抽出
        entities = {}
        # テストファイル名の抽出（CS_TEST_RUN 等の結果に含まれる可能性がある）
        test_file = context.get("analysis", {}).get("entities", {}).get("filename", {}).get("value") or \
                    context.get("analysis", {}).get("entities", {}).get("project_path", {}).get("value")

        if test_file:
            entities["test_file"] = {"value": test_file, "confidence": 1.0}
            # project_path も必要
            if os.path.isdir(test_file):
                entities["project_path"] = {"value": test_file, "confidence": 1.0}
            else:
                entities["project_path"] = {"value": os.path.dirname(test_file) or ".", "confidence": 1.0}

        # ダミーのコンテキストを作成して manage_task_state を呼び出し、タスクを開始させる
        dummy_context = {
            "session_id": session_id,
            "analysis": {
                "intent": recovery_intent,
                "entities": entities
            },
            "history": context.get("history", []),
            "errors": []
        }

        updated_context = self.manage_task_state(dummy_context)

        # 試行回数をインクリメントして設定
        if session_id in self.active_tasks:
            self.active_tasks[session_id]["recovery_attempts"] = attempts + 1

        # 元のコンテキストにタスク情報を反映
        context["task"] = updated_context.get("task")
        context["clarification_needed"] = updated_context.get("clarification_needed")
        context["response"] = updated_context.get("response")

        self._log_debug(f"Recovery task '{recovery_intent}' initiated.")
        return context

    def is_recovery_limit_reached(self, session_id: str) -> bool:
        """回復試行回数が制限に達しているか確認"""
        task = self.active_tasks.get(session_id)
        if not task:
            return False
        return task.get("recovery_attempts", 0) >= self.config.max_recovery_attempts

    def get_memory_usage_stats(self) -> dict:
        """メモリ使用量統計の取得"""
        stats = self.session_manager.get_memory_usage_stats()

        if self.metrics:
            stats["metrics_memory"] = self.metrics.get_summary_stats()

        return stats

    def validate_task_integrity(self, session_id: str) -> dict:
        """タスクの整合性を検証"""
        return self.session_manager.validate_integrity(session_id, self.task_definitions)
