# -*- coding: utf-8 -*-
# src/task_manager/task_manager.py

import uuid
import json
import os # Added for file operations
import time

class TaskManager:
    def __init__(self, action_executor=None, log_manager=None, task_definitions_path=None, config_manager=None):
        """
        Initializes the TaskManager.
        """
        from .metrics import TaskManagerMetrics
        from .task_persistence import TaskPersistence
        from .approval_messages import ApprovalMessageGenerator
        from .condition_evaluator import ConditionEvaluator
        from .session_manager import SessionManager
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
            self.CRITICAL_INTENTS = safety_policy.get("destructive_intents", ["FILE_DELETE", "CMD_RUN"])
        else:
            self.CRITICAL_INTENTS = ["FILE_DELETE", "CMD_RUN"]

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
        self.persistence = TaskPersistence(
            storage_dir=self.config.persistence_dir,
            max_age_hours=self.config.max_state_age_hours,
            log_manager=self.log_manager
        ) if self.config.enable_persistence else None

        # 承認メッセージジェネレーター
        self.approval_messages = ApprovalMessageGenerator()

        # 条件評価器
        self.condition_evaluator = ConditionEvaluator()

        # セッション管理
        self.session_manager = SessionManager(self.active_tasks, self.session_last_activity, self.config)

        # Load task definitions
        self.task_definitions = self._load_task_definitions(self.task_definitions_path)

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
            print(f"[TaskManager ERROR] {message}")

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

        # If PROVIDE_CONTENT arrives without an active task but includes a filename,
        # treat it as FILE_CREATE to avoid orphan content intents.
        if not current_task and intent == "PROVIDE_CONTENT":
            fn_entity = entities.get("filename")
            fn_val = fn_entity.get("value") if isinstance(fn_entity, dict) else fn_entity
            if fn_val:
                intent = "FILE_CREATE"
                context["analysis"]["intent"] = "FILE_CREATE"
        
        # --- NEW: Propagate entities from current turn to task parameters ---
        if current_task:
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
        if intent in ["CLARIFICATION_RESPONSE", "AGREE", "DISAGREE"]:
            self._log_debug(f"Processing {intent} for session {session_id}")
            active_task = self.active_tasks.get(session_id)
            if active_task and active_task.get("clarification_needed"):
                self._log_debug(f"Active task found with clarification needed: {active_task['name']}")
                
                # Check for user_response entity (from vector fallback) or directly use intent
                user_response_val = intent
                if isinstance(entities.get("user_response"), dict):
                    user_response_val = entities["user_response"].get("value", intent)
                
                # Temporarily store for evaluation
                active_task["parameters"]["user_response"] = user_response_val

                clarification_task_def = self.task_definitions.get("CLARIFICATION_RESPONSE")
                if clarification_task_def:
                    clarification_eval_context = {
                        "analysis": {"entities": {"user_response": {"value": user_response_val}}},
                        "task": active_task
                    }
                    transitions = clarification_task_def.get("transitions", {}).get("INIT", [])
                    
                    for transition in transitions:
                        if self._evaluate_condition(transition["condition"], clarification_eval_context):
                            if transition["next_state"] == "AGREED":
                                active_task["clarification_needed"] = False
                                active_task["clarification_message"] = None
                                active_task["clarification_type"] = None
                                active_task.pop("awaiting_entity", None)
                                if not active_task.get("approval_history"): active_task["approval_history"] = []
                                active_task["approval_history"].append({"timestamp": time.time(), "action": "APPROVED"})
                                
                                if active_task.get("type") == "COMPOUND_TASK" and active_task.get("state") == "INIT":
                                    active_task["state"] = "IN_PROGRESS"
                                
                                active_task["parameters"].pop("user_response", None)
                                # Reset intent to trigger re-evaluation of the now-approved task
                                context["analysis"]["intent"] = active_task["name"]
                                context["clarification_needed"] = False
                                return self.manage_task_state(context)
                            
                            elif transition["next_state"] == "DISAGREED":
                                self.reset_task(session_id)
                                context["task_cancelled"] = True
                                context["clarification_needed"] = False
                                context["response"] = {"text": "タスクがキャンセルされました。"}
                                return context
        # -------------------------------------------------------------

        conversational_intents = ["GREETING", "PERSONAL_Q", "EMOTIVE", "DEFINITION", "GENERAL", "NO_INTENT", "TIME", "WEATHER", "SMALLTALK", "AGREE", "DISAGREE"] # Add NO_INTENT for cases where intent is not recognized.

        # 永続化からの状態復旧
        if not current_task and self.persistence:
            restored_task = self.persistence.load_task_state(session_id)
            if restored_task:
                self.active_tasks[session_id] = restored_task
                current_task = restored_task
                self._log_debug(f"Restored task state for session {session_id}")
        
        # Handle CANCEL_TASK explicitly
        if intent == "CANCEL_TASK":
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
        if intent in ["CLARIFICATION_RESPONSE", "AGREE", "DISAGREE"]:
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
                    clarification_task_def = self.task_definitions.get("CLARIFICATION_RESPONSE")
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
                                if transition["next_state"] == "AGREED":
                                    self._log_debug("User agreed to task execution")
                                    # User agreed, clear clarification needed flags and re-evaluate the original task
                                    active_task["clarification_needed"] = False
                                    active_task["clarification_message"] = None
                                    
                                    # 承認履歴の記録
                                    if not active_task.get("approval_history"):
                                        active_task["approval_history"] = []
                                    active_task["approval_history"].append({
                                        "timestamp": time.time(),
                                        "action": "APPROVED",
                                        "task_type": active_task.get("type", "SIMPLE_TASK"),
                                        "task_name": active_task.get("name")
                                    })
                                    
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
                                
                                elif transition["next_state"] == "DISAGREED":
                                    # User disagreed, cancel the active task
                                    # 拒否履歴の記録
                                    if not active_task.get("approval_history"):
                                        active_task["approval_history"] = []
                                    active_task["approval_history"].append({
                                        "timestamp": time.time(),
                                        "action": "REJECTED",
                                        "task_type": active_task.get("type", "SIMPLE_TASK"),
                                        "task_name": active_task.get("name")
                                    })
                                    
                                    self.reset_task(session_id)
                                    context["task_cancelled"] = True
                                    context["clarification_needed"] = False # Clarification handled, no longer needed
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

        # 1. Initiate a new task if no active task and a valid task intent is detected
        if not current_task and task_definition:
            if task_definition.get("type") == "COMPOUND_TASK":
                subtasks_definitions = []
                for subtask_def in task_definition.get("subtasks", []):
                    subtasks_definitions.append({
                        "name": subtask_def["name"],
                        "state": "PENDING", # Initial state for subtasks
                        "parameters": {} # Subtask parameters will be filled during its lifecycle
                    })
                current_task = {
                    "id": str(uuid.uuid4()),
                    "name": effective_intent,
                    "type": "COMPOUND_TASK",
                    "state": "INIT", # Overall state of the compound task
                    "parameters": {}, # Parent-level parameters
                    "subtasks": subtasks_definitions,
                    "current_subtask_index": 0,
                    "history": [],
                    "recovery_attempts": 0, # NEW: Track recovery loops
                    "clarification_needed": task_definition.get("require_overall_approval", True),  # Default to True, but allow override
                    "clarification_message": None, # Will be set below if needed
                    "clarification_type": "APPROVAL" if task_definition.get("require_overall_approval", True) else None
                }
                
                # Propagate entities to the new task immediately
                for entity_key, entity_data in entities.items():
                    if entity_data.get("value"):
                        current_task["parameters"][entity_key] = entity_data

                # デバッグ情報
                require_approval = task_definition.get("require_overall_approval", True)
                self._log_debug(f"Compound task {effective_intent}: require_overall_approval={require_approval}, clarification_needed={current_task['clarification_needed']}")
                
                if task_definition.get("require_overall_approval", True):
                    context["clarification_needed"] = True # Set top-level clarification_needed only if approval is required
                    # 複合タスクの承認メッセージをcontextにも設定
                    approval_message = self.approval_messages.generate_overall_approval_message(effective_intent, current_task["parameters"], self.task_definitions)
                    current_task["clarification_message"] = approval_message  # 実際のメッセージを設定
                    current_task["clarification_type"] = "APPROVAL"
                    context["response"] = {"text": approval_message}
                    # LOG
                    if self.log_manager:
                        self.log_manager.log_event("clarification_needed", {"message": approval_message}, level="INFO")
                    self._log_debug(f"Set context clarification_needed=True for compound task {effective_intent}")
                    self._log_debug(f"Set approval message: {approval_message}")
            else: # Regular (simple) task
                current_task = {
                    "id": str(uuid.uuid4()),
                    "name": effective_intent,
                    "type": "SIMPLE_TASK", # Explicitly mark as simple task
                    "state": "INIT",
                    "parameters": {},
                    "history": [],
                    "clarification_needed": False,
                    "clarification_message": None,
                    "clarification_type": None
                }
            self.active_tasks[session_id] = current_task
            
            # メトリクス記録
            if self.metrics:
                self.metrics.start_task(session_id, effective_intent, task_definition.get("type", "SIMPLE_TASK"))
            
            # 永続化
            if self.persistence:
                self.persistence.save_task_state(session_id, current_task)
            
            context["analysis"]["task_initiated"] = True # For logging/tracking
            self._log_debug(f"Created new task: {effective_intent} for session {session_id}")
            
            for entity_key, entity_data in entities.items():
                if entity_data.get("value"):
                    current_task["parameters"][entity_key] = entity_data
            # --- END NEW ---
        
        if current_task:
            context["task"] = current_task # Set it early so _evaluate_condition can see it
            task_name = current_task["name"]
            task_type = current_task.get("type", "SIMPLE_TASK") # Default to SIMPLE_TASK for old definitions
            task_def = self.task_definitions.get(task_name)

            if not task_def:
                context["errors"].append({
                    "module": "task_manager",
                    "message": f"タスク定義 '{task_name}' が見つかりません。"
                })
                self._update_clarification_status(context)
                return context

            # --- START COMPOUND TASK LOGIC ---
            if task_type == "COMPOUND_TASK":
                # Check if overall approval is needed first
                if current_task.get("state") == "INIT" and current_task.get("clarification_needed"):
                    # Overall approval is needed, return early
                    self._update_clarification_status(context)
                    return context
                
                sub_task_index = current_task.get("current_subtask_index", 0)

                # If we've completed all subtasks, the compound task is effectively done for state management
                if sub_task_index >= len(current_task.get("subtasks", [])):
                    # All sub-tasks are done, no more state management needed here.
                    self._update_clarification_status(context)
                    return context
                
                sub_task = current_task["subtasks"][sub_task_index]
                sub_task_def = self.task_definitions.get(sub_task["name"])

                if not sub_task_def:
                    context["errors"].append({
                        "module": "task_manager",
                        "message": f"複合タスク '{current_task['name']}' のサブタスク '{sub_task['name']}' の定義が見つかりません。"
                    })
                    self.reset_task(session_id)
                    self._update_clarification_status(context)
                    return context

                if sub_task: # Process current sub-task regardless of state
                    
                    # 1. Propagate entities from parent and current turn (only if not already ready)
                    if sub_task.get("state") in ["PENDING", "INIT"]:
                        sub_task.setdefault("parameters", {})
                        
                        # Use parameter_mapping from the parent task's definition
                        parent_task_def = self.task_definitions.get(current_task["name"], {})
                        subtask_info_from_def = parent_task_def.get("subtasks", [])[sub_task_index]
                        param_mapping = subtask_info_from_def.get("parameter_mapping", {})

                        for sub_param, parent_param in param_mapping.items():
                            if parent_param in current_task["parameters"]:
                                sub_task["parameters"][sub_param] = current_task["parameters"][parent_param]

                        # Current turn entities can also fill in missing parameters
                        for entity_key, entity_data in entities.items():
                            if entity_data.get("value"):
                                sub_task["parameters"][entity_key] = entity_data
                                
                        # 2. Create a temporary context for evaluating the sub-task's state
                        # We create a new context for the sub_task evaluation to avoid side-effects
                        sub_task_eval_context = {
                            "analysis": {"entities": sub_task["parameters"]},
                            # _evaluate_condition uses context['task']['parameters'] as a fallback
                            "task": sub_task 
                        }

                        # 3. Evaluate transitions for the sub-task
                        current_sub_state = sub_task.get("state", "INIT")
                        if current_sub_state == "PENDING": current_sub_state = "INIT"

                        transitions = sub_task_def.get("transitions", {}).get(current_sub_state, [])
                        for transition in transitions:
                            if self._evaluate_condition(transition["condition"], sub_task_eval_context):
                                old_state = sub_task.get("state", "INIT")
                                new_state = transition["next_state"]
                                sub_task["state"] = new_state
                                sub_task["clarification_needed"] = False # Reset on successful transition
                                sub_task["clarification_message"] = None
                                sub_task["clarification_type"] = None
                                
                                # ログ記録
                                self._log_state_transition(session_id, old_state, new_state, f"{current_task['name']}.{sub_task['name']}")
                                
                                # 永続化
                                if self.persistence:
                                    self.persistence.save_task_state(session_id, current_task)
                                break 
                    
                    # --- NEW: Level 2 Approval Check for Critical Subtasks (check regardless of state transition) ---

                    if (sub_task["state"] == "READY_FOR_EXECUTION" and 
                        sub_task["name"] in self.CRITICAL_INTENTS and 
                        not sub_task.get("clarification_needed", False) and
                        current_task.get("state") != "IN_PROGRESS"):  # Skip if overall task already approved

                        sub_task["clarification_needed"] = True
                        # より具体的な承認メッセージを生成
                        sub_task["clarification_message"] = self.approval_messages.generate_critical_subtask_message(
                            current_task.get("name", "不明なタスク"),
                            sub_task.get("name", "不明なサブタスク"),
                            sub_task.get("parameters", {}),
                            self.task_definitions
                        )
                        sub_task["clarification_type"] = "APPROVAL"
                        current_task["clarification_type"] = "APPROVAL"
                        context["clarification_needed"] = True # <--- This line is supposed to set it to True
                        
                        # メトリクス記録
                        if self.metrics:
                            self.metrics.record_approval_request(session_id, "CRITICAL_SUBTASK")
                        # context["response"]["text"] will be set by Pipeline calling ResponseGenerator

                    # --- END NEW ---

                    # 4. If not ready and not already asking for approval, check for missing entities and set clarification
                    if not context.get("clarification_needed") and sub_task["state"] != "READY_FOR_EXECUTION":
                        required = sub_task_def.get("required_entities", [])
                        missing_entities = [req for req in required if req not in sub_task["parameters"] or not sub_task["parameters"].get(req)]
                        
                        if missing_entities:
                            first_missing = missing_entities[0]
                            clarification_msgs = sub_task_def.get("clarification_messages", {})
                            message = clarification_msgs.get(first_missing, f"複合タスク「{current_task['name']}」のサブタスク「{sub_task['name']}」で、情報「{first_missing}」が必要です。")

                            sub_task["clarification_needed"] = True
                            sub_task["clarification_message"] = message
                            sub_task["clarification_type"] = "MISSING_ENTITY"
                            sub_task["awaiting_entity"] = first_missing
                            context["clarification_needed"] = True
                            context.setdefault("response", {})
                            context["response"]["text"] = message
                        else:
                            # If no specific entities are missing but not ready, something is wrong with transition logic
                            # Or it's just awaiting more info without a specific prompt
                            sub_task["clarification_needed"] = False
                            sub_task["clarification_message"] = None
                            sub_task["clarification_type"] = None
                            sub_task.pop("awaiting_entity", None)


                # Update the main task structure and return
                current_task["subtasks"][sub_task_index] = sub_task
                context["task"] = current_task

                # Propagate clarification_needed from the current sub_task to the top-level context
                if sub_task.get("clarification_needed"):
                    context["clarification_needed"] = True
                
                return context
            # --- END COMPOUND TASK LOGIC ---

            # The rest of the logic is for SIMPLE tasks.
            # 1. Populate/update entities for the simple task FIRST
            for entity_key, entity_data in entities.items():
                if isinstance(entity_data, dict) and entity_data.get("value"):
                    current_task["parameters"][entity_key] = entity_data
                elif isinstance(entity_data, str):
                    current_task["parameters"][entity_key] = {"value": entity_data, "confidence": 1.0}
            
            # 2. Transition state for the simple task SECOND
            current_state = current_task["state"]
            transitions = task_def.get("transitions", {}).get(current_state, [])
            
            for transition in transitions:
                if self._evaluate_condition(transition["condition"], context):
                    old_state = current_task.get("state", "INIT")
                    new_state = transition["next_state"]
                    current_task["state"] = new_state
                    current_task["clarification_needed"] = False
                    current_task["clarification_message"] = None
                    current_task["clarification_type"] = None
                    current_task.pop("awaiting_entity", None)
                    self._log_state_transition(session_id, old_state, new_state, current_task["name"])
                    if self.persistence: self.persistence.save_task_state(session_id, current_task)
                    break
            
            # 3. Check for missing entities THIRD
            if current_task["state"] != "READY_FOR_EXECUTION":

                required = task_def.get("required_entities", [])
                missing_entities = []
                for req in required:
                    val = current_task["parameters"].get(req)
                    is_missing = not val or (isinstance(val, dict) and not val.get("value"))
                    if is_missing:
                        missing_entities.append(req)

                if missing_entities:
                    first_missing = missing_entities[0]
                    clarification_msgs = task_def.get("clarification_messages", {})
                    message = clarification_msgs.get(first_missing, f"タスク「{task_name}」で、情報「{first_missing}」が必要です。")

                    current_task["clarification_needed"] = True
                    current_task["clarification_message"] = message
                    current_task["clarification_type"] = "MISSING_ENTITY"
                    current_task["awaiting_entity"] = first_missing
                    context["clarification_needed"] = True
                    
                    # LOG
                    if self.log_manager:
                        self.log_manager.log_event("clarification_needed", {"message": message}, level="INFO")
                    
                    # --- NEW: Flag the specific entity we are waiting for ---
                    context["analysis"]["awaiting_entity"] = first_missing
                    # -------------------------------------------------------


                    
                    # メトリクス記録
                    if self.metrics:
                        self.metrics.record_approval_request(session_id, "MISSING_ENTITY")
                    context.setdefault("response", {})
                    context["response"]["text"] = message

            context["task"] = current_task

        if current_task and current_task.get("state") == "READY_FOR_EXECUTION" and not current_task.get("clarification_needed"):
            context["analysis"]["intent"] = current_task.get("name")

        self._update_clarification_status(context)
        return context

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
        recovery_intent = "RECOVERY_FROM_TEST_FAILURE" # 現時点ではテスト失敗に特化
        
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
