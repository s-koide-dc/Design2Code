# -*- coding: utf-8 -*-
# src/clarification_manager/clarification_manager.py

import json
import os

class ClarificationManager:
    def __init__(self, action_executor, log_manager, clarification_thresholds=None, max_clarification_attempts=3):
        """
        Initializes the Clarification Manager with thresholds and max attempts.
        Args:
            clarification_thresholds (dict): Dictionary with 'intent' and 'entity' confidence thresholds.
            max_clarification_attempts (int): Maximum number of clarification turns for a single request.
        """
        self._intent_threshold = clarification_thresholds.get("intent", 0.75) if clarification_thresholds else 0.75
        self._entity_threshold = clarification_thresholds.get("entity", 0.75) if clarification_thresholds else 0.75
        self._max_clarification_attempts = max_clarification_attempts # Make it an internal attribute

        self.action_executor = action_executor
        self.log_manager = log_manager
        self.clarification_history = {} # Tracks attempts per original_text_id or session_id
        
        # Load clarification templates - assuming they will be in knowledge_base.json or similar
        self.clarification_templates = self._load_clarification_templates()

    @property
    def intent_threshold(self):
        return self._intent_threshold

    @intent_threshold.setter
    def intent_threshold(self, value):
        self._intent_threshold = value

    @property
    def entity_threshold(self):
        return self._entity_threshold

    @entity_threshold.setter
    def entity_threshold(self, value):
        self._entity_threshold = value

    @property
    def max_clarification_attempts(self):
        return self._max_clarification_attempts

    @max_clarification_attempts.setter
    def max_clarification_attempts(self, value):
        self._max_clarification_attempts = value

    def _load_clarification_templates(self):
        """Loads clarification templates from knowledge_base.json or a dedicated file."""
        filepath = os.path.join(os.getcwd(), 'resources', 'knowledge_base.json') # Assuming templates are here
        if not os.path.exists(filepath):
            return {
                "default_clarification": "申し訳ありませんが、意図が明確ではありません。もう少し詳しく教えていただけますか？",
                "low_intent_confidence": "意図が明確ではありません。'{intent}'（信頼度:{conf:.2f}）でよろしいでしょうか？",
                "low_entity_confidence": "エンティティ'{entity_key}'（値:'{entity_value}'、信頼度:{conf:.2f}）が不明確です。よろしいでしょうか？",
                "ambiguous_intent": "おっしゃる意図は'{intent1}'（信頼度:{conf1:.2f}）でしょうか、それとも'{intent2}'（信頼度:{conf2:.2f}）でしょうか？",
                "missing_entity": {
                    "default": "{entity_key}を教えていただけますか？",
                    "filename": "ファイル名を教えていただけますか？",
                    "content": "ファイルの内容を教えていただけますか？",
                    "project_path": "プロジェクトのパスを教えていただけますか？"
                },
                "max_attempts_reached": "申し訳ありません。意図が特定できませんでした。必要な情報の一覧を提示しますので、手動で操作してください.\n不足情報: {missing_info}"
            }
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                kb = json.load(f)
                return kb.get("clarification_templates", {
                    "default_clarification": "申し訳ありませんが、意図が明確ではありません。もう少し詳しく教えていただけますか？",
                    "ambiguous_intent": "おっしゃる意図は'{intent1}'（信頼度:{conf1:.2f}）でしょうか、それとも'{intent2}'（信頼度:{conf2:.2f}）でしょうか？",
                    "low_intent_confidence": "意図が明確ではありません。'{intent}'（信頼度:{conf:.2f}）でよろしいでしょうか？",
                    "low_entity_confidence": "エンティティ'{entity_key}'（値:'{entity_value}'、信頼度:{conf:.2f}）が不明確です。よろしいでしょうか？",
                    "missing_entity": {
                        "default": "{entity_key}を教えていただけますか？",
                        "filename": "ファイル名を教えていただけますか？",
                        "content": "ファイルの内容を教えていただけますか？",
                        "project_path": "プロジェクトのパスを教えていただけますか？"
                    },
                    "multiple_entities": "'{entity_key}'として複数の値が検出されました: {entity_values}。どれを操作しますか？",
                    "max_attempts_reached": "申し訳ありません。意図が特定できませんでした。必要な情報の一覧を提示しますので、手動で操作してください.\n不足情報: {missing_info}"
                })
        except Exception as e:
            self.log_manager.log_event(
                "clarification_template_load_error",
                {"filepath": filepath, "error": str(e)},
                "ERROR"
            )
            return {
                "default_clarification": "申し訳ありませんが、意図が明確ではありません。もう少し詳しく教えていただけますか？",
                "low_intent_confidence": "意図が明確ではありません。'{intent}'（信頼度:{conf:.2f}）でよろしいでしょうか？",
                "low_entity_confidence": "エンティティ'{entity_key}'（値:'{entity_value}'、信頼度:{conf:.2f}）が不明確です。よろしいでしょうか？",
                "ambiguous_intent": "おっしゃる意図は'{intent1}'（信頼度:{conf1:.2f}）でしょうか、それとも'{intent2}'（信頼度:{conf2:.2f}）でしょうか？",
                "missing_entity": {
                    "default": "{entity_key}を教えていただけますか？",
                    "filename": "ファイル名を教えていただけますか？",
                    "content": "ファイルの内容を教えていただけますか？",
                    "project_path": "プロジェクトのパスを教えていただけますか？"
                },
                "max_attempts_reached": "申し訳ありません。意図が特定できませんでした。必要な情報の一覧を提示しますので、手動で操作してください.\n不足情報: {missing_info}"
            }

    def manage_clarification(self, context: dict) -> dict:
        """
        Checks for ambiguity or missing information and generates a clarification response.
        Updates the context with clarification status and messages.
        """
        context.setdefault("analysis", {})
        context.setdefault("response", {})
        context.setdefault("errors", [])
        context.setdefault("pipeline_history", [])
        
        # Preserve clarification_needed if already set by TaskManager or others
        if not context.get("clarification_needed"):
            context["clarification_needed"] = False
            
        context["pipeline_history"].append("clarification_manager")

        # Ensure missing_entity template is a dict (robustness for varying knowledge_base.json or default templates)
        if isinstance(self.clarification_templates.get("missing_entity"), str):
            self.clarification_templates["missing_entity"] = {
                "default": self.clarification_templates["missing_entity"], # Use existing string as default
                "filename": "ファイル名を教えていただけますか？",
                "content": "ファイルの内容を教えていただけますか？",
                "project_path": "プロジェクトのパスを教えていただけますか？"
            }

        intent = context["analysis"].get("intent")
        intent_confidence = context["analysis"].get("intent_confidence", 0.0)
        entities = context["analysis"].get("entities", {})
        current_task = context.get("task")
        
        # If clarification is already explicitly set in context (e.g. by TaskManager), respect it.
        if context.get("clarification_needed"):
            # Ensure response text is set if clarification_needed is True but response is empty
            if not context["response"].get("text") and context.get("task", {}).get("clarification_message"):
                context["response"]["text"] = context["task"]["clarification_message"]
            return context
        
        # If a task is ready for execution, do not block on low intent confidence.
        if current_task and current_task.get("state") == "READY_FOR_EXECUTION":
            return context

        internal_session_id = context.get("session_id") or hash(context.get("original_text", "")) 
            
        current_attempts = self.clarification_history.get(internal_session_id, 0)
        
        
        clarification_message = None

        # 1. Check for errors in context["errors"] first
        if context.get("errors"):
            error_messages = [e.get("message", "不明なエラー") for e in context["errors"]]
            clarification_message = "エラーが発生しました: " + " ".join(error_messages)
            self.log_manager.log_event(
                "clarification_needed",
                {"reason": "external_error", "errors": error_messages},
                "ERROR"
            )
        
        # 2. Check max clarification attempts
        if not clarification_message and current_attempts >= self._max_clarification_attempts:
            missing_info_list = []
            if intent: # Only check for required entities if intent is known
                required_entities = self.action_executor.get_required_entities_for_intent(intent)
                for req_entity in required_entities:
                    entity_data = entities.get(req_entity)
                    if not entity_data:
                        missing_info_list.append(req_entity)
                    elif isinstance(entity_data, dict):
                        if not entity_data.get("value"):
                            missing_info_list.append(req_entity)
                    else: # String or other type
                        if not entity_data:
                            missing_info_list.append(req_entity)
            
            clarification_message = self.clarification_templates["max_attempts_reached"].format(
                missing_info=", ".join(missing_info_list) if missing_info_list else "なし"
            )
            self.log_manager.log_event(
                "clarification_needed",
                {"reason": "max_attempts_reached", "session_id": internal_session_id, "missing_info": missing_info_list},
                "WARNING"
            )
            self.clarification_history[internal_session_id] = 0 # Reset for next new original_text - FIX 2
            
            # If max attempts reached, return context immediately with the clarification message
            context["clarification_needed"] = True
            context["response"]["text"] = clarification_message
            return context
        
        # 3. Check Intent Ambiguity (only if no direct error or max attempts reached)
        if not clarification_message and intent_confidence < self._intent_threshold:
            clarification_message = self.clarification_templates["low_intent_confidence"].format(
                intent=intent, conf=intent_confidence
            )
            self.log_manager.log_event(
                "clarification_needed",
                {"reason": "low_intent_confidence", "intent": intent, "confidence": intent_confidence},
                "INFO"
            )

        # 4. Check Entity Ambiguity/Missing (only if no direct error, max attempts, or intent ambiguity)
        if not clarification_message: # Intent is clear enough, check entities
            # Check for low confidence entities
            for key, entity_data in entities.items():
                if entity_data.get("confidence", 1.0) < self._entity_threshold:
                    clarification_message = self.clarification_templates["low_entity_confidence"].format(
                        entity_key=key, entity_value=entity_data.get("value", ""), conf=entity_data.get("confidence", 0.0)
                    )
                    self.log_manager.log_event(
                        "clarification_needed",
                        {"reason": "low_entity_confidence", "entity_key": key, "entity_value": entity_data.get("value", ""), "confidence": entity_data.get("confidence", 0.0)},
                        "INFO"
                    )
                    break
            
            # Check for missing required entities
            if not clarification_message and intent: # Only check if intent is known
                required_entities = self.action_executor.get_required_entities_for_intent(intent)
                
                # Check both top-level entities and active subtask parameters
                current_task = context.get("task", {})
                check_params = entities
                if current_task.get("type") == "COMPOUND_TASK":
                    sub_idx = current_task.get("current_subtask_index", 0)
                    subtasks = current_task.get("subtasks", [])
                    if sub_idx < len(subtasks):
                        active_sub_params = subtasks[sub_idx].get("parameters", {})
                        # Create a temporary merged dict for checking
                        check_params = entities.copy()
                        check_params.update(active_sub_params)

                for req_entity in required_entities:
                    entity_data = check_params.get(req_entity)
                    is_missing = False
                    if not entity_data:
                        is_missing = True
                    elif isinstance(entity_data, dict):
                        if not entity_data.get("value"):
                            is_missing = True
                    else: # String or other type
                        if not entity_data:
                            is_missing = True

                    if is_missing:
                        clarification_message = self.clarification_templates["missing_entity"].get(
                            req_entity, 
                            self.clarification_templates["missing_entity"]["default"]
                        ).format(entity_key=req_entity)
                        self.log_manager.log_event(
                            "clarification_needed",
                            {"reason": "missing_entity", "entity_key": req_entity, "intent": intent},
                            "INFO"
                        )
                        break # Only ask for one missing entity at a time for simplicity
        
        if clarification_message:
            context["clarification_needed"] = True
            context["response"]["text"] = clarification_message
            # If it's a max_attempts_reached message, always reset attempts
            if "max_attempts_reached" in clarification_message:
                self.clarification_history[internal_session_id] = 0
            # Otherwise, increment attempts if no errors
            elif not context.get("errors"):
                self.clarification_history[internal_session_id] = current_attempts + 1
            else:
                self.clarification_history[internal_session_id] = 0 # Reset attempts for actual errors
        else:
            self.clarification_history[internal_session_id] = 0 # Clear attempts if no clarification needed
            self.log_manager.log_event(
                "clarification_not_needed",
                {"session_id": internal_session_id, "intent": intent},
                "INFO"
            )
        
        return context

# Dummy for ActionExecutor, would be replaced by actual ActionExecutor.get_required_entities
class DummyActionExecutor:
    def get_required_entities(self, intent):
        if intent == "FILE_CREATE":
            return ["filename", "content"]
        elif intent == "FILE_READ":
            return ["filename"]
        elif intent == "CMD_RUN":
            return ["command"]
        return []

class DummyLogManager:
    def log_event(self, event_type, data, level):
        print(f"[DummyLog] {event_type}: {data}")

if __name__ == '__main__':
    from src.action_executor.action_executor import ActionExecutor # Import actual ActionExecutor

    # Initialize ActionExecutor once
    ae = ActionExecutor()
    lm = DummyLogManager()

    # Test cases for ClarificationManager
    cm = ClarificationManager(action_executor=ae, log_manager=lm, clarification_thresholds={"intent": 0.7, "entity": 0.7})

    print("--- Test Case 1: Low Intent Confidence ---")
    context1 = {
        "original_text": "曖昧な指示",
        "analysis": {"intent": "AMBIGUOUS_ACTION", "intent_confidence": 0.6},
    }
    result1 = cm.manage_clarification(context1)
    print(result1["response"]["text"])
    assert result1["clarification_needed"] == True

    print("\n--- Test Case 2: Low Entity Confidence ---")
    context2 = {
        "original_text": "ファイル A を編集",
        "analysis": {
            "intent": "FILE_EDIT", "intent_confidence": 0.9,
            "entities": {"filename": {"value": "file A", "confidence": 0.6}}
        },
    }
    result2 = cm.manage_clarification(context2)
    print(result2["response"]["text"])
    assert result2["clarification_needed"] == True

    print("\n--- Test Case 3: Missing Required Entity (FILE_CREATE) ---")
    context3 = {
        "original_text": "ファイルを作って",
        "analysis": {
            "intent": "FILE_CREATE", "intent_confidence": 0.9,
            "entities": {"filename": {"value": "new.txt", "confidence": 0.9}} # Content is missing
        },
    }
    result3 = cm.manage_clarification(context3)
    print(result3["response"]["text"])
    assert result3["clarification_needed"] == True
    assert "content" in result3["response"]["text"] # Check if it asks for content

    print("\n--- Test Case 4: Max Attempts Reached ---")
    context4 = {
        "original_text": "繰り返しの曖昧な指示",
        "analysis": {"intent": "AMBIGUOUS_ACTION", "intent_confidence": 0.6},
    }
    cm.clarification_history[hash("繰り返しの曖昧な指示")] = cm.max_clarification_attempts - 1 # Simulate 2 attempts
    result4 = cm.manage_clarification(context4)
    print(result4["response"]["text"])
    assert result4["clarification_needed"] == True
    assert "手動で操作してください" in result4["response"]["text"]
    
    print("\n--- Test Case 5: No Clarification Needed ---")
    context5 = {
        "original_text": "明確な指示",
        "analysis": {"intent": "FILE_CREATE", "intent_confidence": 0.95,
                     "entities": {"filename": {"value": "test.txt", "confidence": 0.95},
                                  "content": {"value": "hello", "confidence": 0.95}}
        },
    }
    result5 = cm.manage_clarification(context5)
    print(result5.get("response", {}).get("text", "No clarification needed"))
    assert result5["clarification_needed"] == False
