# -*- coding: utf-8 -*-
# src/planner/planner.py

import os
import json

from src.utils.context_utils import _get_context_summary
from src.safety.safety_policy_validator import SafetyPolicyValidator, SafetyCheckStatus, RiskLevel

class Planner:
    def __init__(self, action_executor, log_manager, autonomous_learning=None, intent_entity_thresholds=None, retry_rules_path=None, config_manager=None):
        """
        Initializes the Planner with an ActionExecutor instance and thresholds.
        """
        self.action_executor = action_executor
        self.log_manager = log_manager
        self.autonomous_learning = autonomous_learning
        self.config_manager = config_manager
        self.intent_threshold = intent_entity_thresholds.get("intent", 0.8) if intent_entity_thresholds else 0.8
        self.entity_threshold = intent_entity_thresholds.get("entity", 0.8) if intent_entity_thresholds else 0.8

        rr_path = retry_rules_path
        if not rr_path and config_manager:
            self.retry_rules = config_manager.get_retry_rules()
        else:
            if not rr_path: rr_path = "resources/retry_rules.json"
            self.retry_rules = self._load_retry_rules(rr_path)

        self.safety_validator = SafetyPolicyValidator(self.action_executor, config_manager=config_manager)

        # Define mapping from intent to ActionExecutor method names
        self.intent_to_action_method = {
            "FILE_CREATE": "_create_file",
            "FILE_READ": "_read_file",
            "FILE_APPEND": "_append_file",
            "FILE_DELETE": "_delete_file",
            "FILE_MOVE": "_move_file",
            "FILE_COPY": "_copy_file",
            "LIST_DIR": "_list_dir",
            "GET_CWD": "_get_cwd",
            "CMD_RUN": "_run_command",
            "CS_TEST_RUN": "_run_dotnet_test",
            "CS_ANALYZE": "_analyze_csharp",
            "GENERATE_TESTS": "_generate_test_cases",
            "CS_QUERY_ANALYSIS": "_query_csharp_analysis_results",
            "CS_IMPACT_SCOPE": "_query_csharp_analysis_results",
            "MEASURE_COVERAGE": "_measure_coverage",
            "ANALYZE_COVERAGE_GAPS": "_analyze_coverage_gaps",
            "GENERATE_COVERAGE_REPORT": "_generate_coverage_report",
            "ANALYZE_REFACTORING": "_analyze_refactoring",
            "SUGGEST_REFACTORING": "_suggest_refactoring",
            "APPLY_REFACTORING": "_apply_refactoring",
            "ANALYZE_TEST_FAILURE": "_analyze_test_failure",
            "EXECUTE_GOAL_DRIVEN_TDD": "_execute_goal_driven_tdd",
            "APPLY_CODE_FIX": "_apply_code_fix",
            "RUN_LEARNING_CYCLE": "_run_learning_cycle",
            "MANAGE_KNOWLEDGE": "_manage_knowledge",
            "REVERSE_DICTIONARY_SEARCH": "_reverse_dictionary_lookup",
            "DOC_GEN": "_generate_design_doc",
            "DOC_REFINE": "_refine_design_doc",
        }

    def _load_retry_rules(self, filepath: str) -> list:
        """Loads retry rules from a JSON file."""
        if not os.path.exists(filepath):
            return []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f).get("retry_rules", [])
        except Exception as e:
            return []

    def _load_project_rules(self) -> dict:
        """Loads project rules from resources/project_rules.json."""
        rule_path = os.path.join("resources", "project_rules.json")
        if not os.path.exists(rule_path):
            return {}
        try:
            with open(rule_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _apply_project_rules(self, intent: str, parameters: dict) -> dict:
        """
        Applies project rules to the parameters.
        Returns a dictionary of warnings or adjustments.
        """
        rules = self._load_project_rules()
        if not rules:
            return {}
            
        warnings = []
        adjustments = {}
        
        # 1. Naming Convention Check (File Create/Rename)
        if intent in ["FILE_CREATE", "FILE_MOVE", "FILE_COPY"]:
            # Retrieve filename from potential parameter keys
            filename = parameters.get("filename") or parameters.get("destination_filename")
            if filename:
                naming = rules.get("naming_conventions", {}).get("files", {})
                basename = os.path.basename(filename)
                
                # Python snake_case check
                if filename.endswith(".py"):
                    # Simple check: no uppercase letters allowed for snake_case
                    if any(c.isupper() for c in basename):
                        warnings.append(f"Filename '{basename}' violates Python naming convention (snake_case required).")
                        # Proposal: Convert to snake_case (simplified)
                        import re
                        new_name = re.sub(r'(?<!^)(?=[A-Z])', '_', basename).lower()
                        if new_name != basename:
                            adjustments["suggested_filename"] = os.path.join(os.path.dirname(filename), new_name)

                # C# PascalCase check
                elif filename.endswith(".cs"):
                     if basename[0].islower():
                        warnings.append(f"Filename '{basename}' violates C# naming convention (PascalCase required).")
                        new_name = basename[0].upper() + basename[1:]
                        adjustments["suggested_filename"] = os.path.join(os.path.dirname(filename), new_name)

        return {"warnings": warnings, "adjustments": adjustments}

    def create_plan(self, context: dict) -> dict:
        """
        Creates a plan based on the detected intent and extracted entities.
        """
        context.setdefault("errors", [])
        
        # --- NEW: Check for errors in history if current turn doesn't have result yet ---
        previous_action_result = context.get("action_result", {})
        if not previous_action_result:
            history = context.get("history", [])
            if history:
                last_entry = history[-1]
                if last_entry.get("action_result", {}).get("status") == "error":
                    previous_action_result = last_entry["action_result"]
        # ----------------------------------------------------------------------------

        if context.get("errors"):
            return context

        self.log_manager.log_event("planner_create_plan_start", {"session_id": context.get("session_id"), "incoming_context_summary": _get_context_summary(context)}, level="DEBUG")

        current_task = context.get("task", {})
        task_type = current_task.get("type", "SIMPLE_TASK") if current_task else None
        task_state = current_task.get("state") if current_task else None

        
        # --- 1. Determine Intent and Entities for Planning ---
        if task_type == "COMPOUND_TASK":
            sub_task_index = current_task.get("current_subtask_index", 0)
            if sub_task_index < len(current_task.get("subtasks", [])):
                active_subtask = current_task["subtasks"][sub_task_index]
                intent = active_subtask["name"]
                entities = active_subtask.get("parameters", {})
                
                intent_confidence = 1.0  # We are certain about the sub-task's intent
                self.log_manager.log_event("planner_compound_subtask", {"session_id": context.get("session_id"), "subtask_name": intent, "subtask_entities": {k: v.get("value") for k, v in entities.items() if isinstance(v, dict)}}, level="DEBUG")
            else:
                self.log_manager.log_event("planner_compound_task_no_active_subtask", {"session_id": context.get("session_id"), "current_task": current_task}, level="DEBUG")
                return context # All subtasks are done
        else: # Simple task or no task
            # If a simple task is now ready, use its intent
            if current_task and task_state == "READY_FOR_EXECUTION":
                intent = current_task["name"]
            else:
                intent = context["analysis"].get("intent")

            intent_confidence = context["analysis"].get("intent_confidence", 0.0)
            analysis_entities = context["analysis"].get("entities", {})
            task_parameters = current_task.get("parameters", {}) if current_task else {}
            
            merged_entities = {}
            merged_entities.update(task_parameters)
            merged_entities.update(analysis_entities)
            
            # --- NEW: Entity Key Mapping ---
            # If the intent requires 'filename' but we have 'project_path', map it.
            if intent == "CS_ANALYZE" and "project_path" in merged_entities and "filename" not in merged_entities:
                merged_entities["filename"] = merged_entities["project_path"]
            
            # If the intent requires 'project_path' but we have 'filename', map it.
            if intent == "CS_TEST_RUN" and "filename" in merged_entities and "project_path" not in merged_entities:
                merged_entities["project_path"] = merged_entities["filename"]
            
            # Default language to 'csharp' for project analysis intents if not specified
            project_intents_requiring_lang = [
                "MEASURE_COVERAGE", "ANALYZE_COVERAGE_GAPS", "GENERATE_COVERAGE_REPORT",
                "ANALYZE_REFACTORING", "SUGGEST_REFACTORING"
            ]
            if intent in project_intents_requiring_lang and "language" not in merged_entities:
                merged_entities["language"] = {"value": "csharp", "confidence": 1.0}
            # -------------------------------

            entities = merged_entities
            self.log_manager.log_event("planner_simple_task", {"session_id": context.get("session_id"), "intent": intent, "entities": {k: v.get("value") for k, v in entities.items() if isinstance(v, dict)}}, level="DEBUG")


        # --- 2. Pre-planning checks and special cases ---
        if intent == "DEFINITION":
            self.log_manager.log_event("planner_definition_intent_bypass", {"session_id": context.get("session_id")}, level="DEBUG")
            return context
        
        # --- NEW: Project Rule Validation ---
        # Extract raw values for validation
        raw_params_for_validation = {}
        for k, v in entities.items():
            if isinstance(v, dict):
                 raw_params_for_validation[k] = v.get("value")
            else:
                 raw_params_for_validation[k] = v
        
        rule_check = self._apply_project_rules(intent, raw_params_for_validation)
        if rule_check.get("warnings"):
            # Add warning to errors list or handle as a soft block
            # For now, we append to warnings but don't block unless strict mode (future)
            # However, if there is a suggestion, we might want to auto-apply or ask user
            for w in rule_check["warnings"]:
                self.log_manager.log_event("planner_rule_warning", {"message": w}, level="WARN")
            
            # If we have suggested filename, update the entity
            if rule_check.get("adjustments", {}).get("suggested_filename"):
                 suggested = rule_check["adjustments"]["suggested_filename"]
                 target_key = "filename" if "filename" in entities else "destination_filename"
                 if target_key in entities:
                     # Update the entity value directly for subsequent processing
                     if isinstance(entities[target_key], dict):
                         entities[target_key]["value"] = suggested
                     else:
                         entities[target_key] = suggested
                     self.log_manager.log_event("planner_rule_adjustment", {"key": target_key, "new_value": suggested}, level="INFO")
        # ------------------------------------

        # --- NEW: Self-Healing / Retry Logic (MOVE TO TOP) ---
        if previous_action_result.get("status") == "error":
            # ONLY trigger healing if intent is same as failing task OR a generic RETRY intent
            last_failed_intent = context.get("history", [{}])[-1].get("analysis", {}).get("intent")
            should_heal = intent == last_failed_intent or intent in ["RETRY", "GENERAL", "AGREE", "DISAGREE"]
            
            if should_heal:
                # 1. Try specialized self-healing first
                healing_plan = self._plan_self_healing(context, previous_action_result)
                if healing_plan:
                    context["plan"] = healing_plan
                    self.log_manager.log_event("planner_self_healing_proposed", {"type": healing_plan.get("healing_type")}, level="INFO")
                    return context

                # 2. Fallback to simple retry rules
                for rule in self.retry_rules:
                    if "original_error_type" in previous_action_result and rule.get("error_type") == previous_action_result["original_error_type"]: 
                        context["plan"] = {
                            "suggestion": "以前の操作が失敗しました。再試行しますか？",
                            "retry_possible": True
                        }
                        self.log_manager.log_event("planner_retry_suggestion", {"context_summary": context.get("original_text"), "previous_error": previous_action_result}, level="INFO")
                        return context
        # --- END NEW ---


        # --- 3. Validate Intent and Entities ---
        is_task_ready_for_execution = False
        if current_task:
            task_to_check = current_task
            if task_type == "COMPOUND_TASK":
                sub_task_index = current_task.get("current_subtask_index", 0)
                if sub_task_index < len(current_task.get("subtasks", [])):
                    task_to_check = current_task['subtasks'][sub_task_index]
            
            is_task_ready_for_execution = task_to_check.get('state') == 'READY_FOR_EXECUTION'


        if not is_task_ready_for_execution and intent_confidence < self.intent_threshold:
            context["errors"].append({"module": "planner", "message": f"意図の信頼度が低すぎます: {intent} (信頼度: {intent_confidence:.2f})"})
            self.log_manager.log_event("planner_low_intent_confidence", {"session_id": context.get("session_id"), "intent": intent, "confidence": intent_confidence}, level="INFO")
            return context

        if not intent or intent not in self.intent_to_action_method:
            context["errors"].append({"module": "planner", "message": f"不明な意図: {intent}"})
            self.log_manager.log_event("planner_unknown_intent", {"session_id": context.get("session_id"), "intent": intent}, level="ERROR")
            return context

        action_method_name = self.intent_to_action_method.get(intent)
        if intent == "FILE_DELETE":
            action_method_name = self.intent_to_action_method.get("BACKUP_AND_DELETE", action_method_name)
        required_entities = self.action_executor.get_required_entities_for_intent(intent)
        
        plan_parameters = {}

        missing_entities = []
        low_confidence_entities = []

        for req_entity_key in required_entities:
            entity_data = entities.get(req_entity_key)
            if not entity_data:
                missing_entities.append(req_entity_key)
                continue

            # Ensure entity_data is a dictionary for .get() access
            if isinstance(entity_data, dict):
                val = entity_data.get("value")
                confidence = entity_data.get("confidence", 0.0)
            else:
                val = entity_data
                confidence = 1.0 # Default confidence for raw values

            if not val:
                missing_entities.append(req_entity_key)
            elif confidence < self.entity_threshold:
                low_confidence_entities.append(req_entity_key)
            else:
                plan_parameters[req_entity_key] = val
        
        # --- NEW: Add optional/contextual parameters ---
        # Always include output_path or query if available, as many project tasks benefit from it
        for optional_key in ["output_path", "query"]:
            if optional_key in entities and optional_key not in plan_parameters:
                val = entities[optional_key]
                if isinstance(val, dict):
                    val = val.get("value")
                plan_parameters[optional_key] = val
        # -----------------------------------------------

        # --- NEW: Impact Scope Query Type and Target Recovery ---
        if intent == "CS_IMPACT_SCOPE":
            plan_parameters["query_type"] = "impact_scope_method"
            if "target_name" not in plan_parameters and "target_name" in entities:
                val = entities["target_name"]
                plan_parameters["target_name"] = val.get("value") if isinstance(val, dict) else val
        # -------------------------------------


        if missing_entities:
            context["errors"].append({"module": "planner", "message": f"必須エンティティが不足しています: {', '.join(missing_entities)}"})
            self.log_manager.log_event("planner_missing_entities", {"session_id": context.get("session_id"), "missing": missing_entities}, level="INFO")
            return context
        
        if low_confidence_entities:
            context["errors"].append({"module": "planner", "message": f"信頼度が低いエンティティがあります: {', '.join(low_confidence_entities)}"})
            self.log_manager.log_event("planner_low_confidence_entities", {"session_id": context.get("session_id"), "low_confidence": low_confidence_entities}, level="INFO")
            return context
        
        # --- 4. Build the Plan ---
        confirmation_needed = False
        is_executing_compound_subtask = (task_type == "COMPOUND_TASK" and task_state == "IN_PROGRESS")
        
        if not is_executing_compound_subtask:
            intent_for_confirmation = current_task.get("name") if task_type == "COMPOUND_TASK" else intent
            # Note: Basic confirmation logic is now handled by SafetyPolicyValidator, but we can keep specific business logic here if needed.
            # For now, we rely on SafetyPolicyValidator mainly, but if we had manual overrides, they'd go here.

        # --- Safety Policy Validation ---
        safety_result = self.safety_validator.validate_action(action_method_name, plan_parameters, intent)
        
        if safety_result.risk_level == RiskLevel.HIGH and not is_executing_compound_subtask:
            confirmation_needed = True

        context["plan"] = {
            "action_method": action_method_name,
            "parameters": plan_parameters,
            "confirmation_needed": confirmation_needed,
            "safety_check_status": safety_result.status.value,
            "safety_message": safety_result.message
        }

        if safety_result.status == SafetyCheckStatus.BLOCK:
            context["errors"].append({"module": "planner", "message": f"Safety Policy Error: {safety_result.message}"})
            self.log_manager.log_event("planner_safety_block", {"session_id": context.get("session_id"), "message": safety_result.message}, level="WARN")
            # We still return context here, but now 'plan' is populated.
            return context
        if task_type == "COMPOUND_TASK":
            context["plan"]["parent_task"] = current_task["name"]
        
        # --- NEW: Impact Analysis Integration ---
        # If we are applying a fix or explicitly asking for impact scope, try to find impacted methods and suggest tests
        if intent in ["APPLY_CODE_FIX", "CS_IMPACT_SCOPE"] and "output_path" in plan_parameters:
            self._refine_plan_with_impact_analysis(context, plan_parameters)
        # ----------------------------------------

        self.log_manager.log_event("planner_plan_created", {"session_id": context.get("session_id"), "plan": context["plan"]}, level="DEBUG")

        return context

    def _plan_self_healing(self, context: dict, error_result: dict) -> dict:
        """
        Analyzes the error and formulates a plan to fix the situation or gather more info.
        """
        error_type = error_result.get("original_error_type") or error_result.get("error_type")
        error_msg = error_result.get("original_error", "") or error_result.get("message", "")
        
        # 0. Query AutonomousLearning for intelligent suggestions (Phase 2)
        if self.autonomous_learning:
            # error_result has everything needed (original_error_type, message)
            suggestion = self.autonomous_learning.get_repair_suggestion(error_result)
            if suggestion:
                action = suggestion.get('action')
                if action == 'ANALYZE_TEST_FAILURE':
                    return {
                        "action_method": "_analyze_test_failure",
                        "parameters": suggestion.get('parameters', {}),
                        "suggestion": suggestion.get('reason', "テスト失敗の自動分析を実行しますか？"),
                        "evidence": suggestion.get('evidence'), # NEW: Propagate evidence
                        "confirmation_needed": True,
                        "healing_type": "KNOWLEDGE_BASE_RECOVERY"
                    }
                elif action == 'RETRY_WITH_ADJUSTMENT':
                    # Retry the *same* action method that failed, but with new parameters
                    # We need to find the previous action method from history
                    # For now, we return a suggestion to user with the new parameters
                    return {
                        "suggestion": f"{suggestion.get('suggestion_text', '再試行を提案します。')} (パラメータ調整あり)",
                        "evidence": suggestion.get('evidence'), # NEW: Propagate evidence
                        "retry_possible": True,
                        "proposed_adjustments": suggestion.get('parameters', {}),
                        "healing_type": "RETRY_RULE_MATCH"
                    }

        # Scenario 1: File Not Found
        if error_type == "FileNotFoundError" or "No such file" in error_msg or "見つかりません" in error_msg:
            # Extract filename from error message or context
            import re
            file_match = re.search(r"'(.*?)'", error_msg)
            # Support Japanese quotes or context fallback
            filename = None
            if file_match:
                filename = file_match.group(1)
            else:
                # Try finding file pattern in Japanese error msg
                file_match_jp = re.search(r"ファイル '(.*?)'", error_msg)
                filename = file_match_jp.group(1) if file_match_jp else context.get("analysis", {}).get("entities", {}).get("filename", {}).get("value")
            
            if filename:
                # Ensure it's just the value string if it was a dict
                if isinstance(filename, dict):
                    filename = filename.get("value")
                self.log_manager.log_event("planner_self_healing_file_not_found", {"filename": filename}, level="INFO")
                # Suggest listing the directory to find the correct file
                return {
                    "action_method": "_list_dir",
                    "parameters": {"directory": os.path.dirname(filename) or "."},
                    "suggestion": f"ファイル '{filename}' が見つかりませんでした。ディレクトリの一覧を確認して、正しいファイルを探しますか？",
                    "confirmation_needed": True,
                    "healing_type": "FILE_NOT_FOUND_RECOVERY"
                }

        # Scenario 2: C# Build Error (already handled by FixEngine in TDD, but can be integrated here for general commands)
        if "CS" in error_msg and error_type == "subprocess.CalledProcessError":
             # This could trigger a more general fix attempt
             pass

        return None

    def _refine_plan_with_impact_analysis(self, context: dict, parameters: dict):
        """
        Uses dependency graph to identify impacted methods and potentially add test tasks.
        """
        output_path = parameters.get("output_path")
        target_name = parameters.get("target_name")
        
        # --- NEW: Recover from history if missing in current context ---
        if not target_name or not output_path:
            history = context.get("history", [])
            for past_entry in reversed(history):
                past_entities = past_entry.get("entities", {})
                if not target_name and "target_name" in past_entities:
                    target_name = past_entities["target_name"].get("value")
                if not output_path and "output_path" in past_entities:
                    output_path = past_entities["output_path"].get("value")
                if target_name and output_path:
                    break
        # -------------------------------------------------------------
        
        if not output_path or not target_name:
            return

        self.log_manager.log_event("planner_impact_analysis_start", {"target": target_name, "output_path": output_path}, level="DEBUG")
        
        try:
            # Query ActionExecutor for impact scope
            query_params = {
                "output_path": output_path,
                "query_type": "impact_scope_method",
                "target_name": target_name
            }
            
            # Create a temporary context for query
            temp_context = {"session_id": context.get("session_id"), "analysis": {"entities": {}}}
            query_result_context = self.action_executor._query_csharp_analysis_results(temp_context, query_params)
            
            if query_result_context.get("action_result", {}).get("status") == "success":
                impacted_methods = query_result_context["action_result"].get("impacted_methods", [])
                if impacted_methods:
                    context["plan"]["impacted_methods"] = impacted_methods
                    self.log_manager.log_event("planner_impact_detected", {"count": len(impacted_methods)}, level="INFO")
                    
                    # Logic to suggest additional tests can go here
                    if len(impacted_methods) > 0:
                        # Query associated tests
                        test_query_params = {
                            "output_path": output_path,
                            "query_type": "find_tests_for_methods",
                            "target_name": ",".join(impacted_methods)
                        }
                        test_query_result = self.action_executor._query_csharp_analysis_results(temp_context, test_query_params)
                        
                        if test_query_result.get("action_result", {}).get("status") == "success":
                            associated_tests = test_query_result["action_result"].get("associated_tests", [])
                            
                            # --- NEW: Also check if impacted_methods themselves contain tests ---
                            for m in impacted_methods:
                                if "Test" in m and not any(t.get("test_class") and t["test_class"] in m for t in associated_tests):
                                    associated_tests.append({
                                        "target_method": m,
                                        "test_class": m.rsplit('.', 1)[0],
                                        "test_file": "Unknown" 
                                    })
                            
                            if associated_tests:
                                context["plan"]["suggested_tests"] = associated_tests
                                # Filter out "Unknown" files for the display message
                                display_files = [os.path.basename(t["test_file"]) for t in associated_tests if t.get("test_file") != "Unknown"]
                                if not display_files:
                                    # Fallback to class names if files unknown
                                    display_files = [t["test_class"].split('.')[-1] for t in associated_tests]
                                
                                context["plan"]["suggestion"] = f"修正により影響を受けるコードのテスト（{', '.join(sorted(list(set(display_files))))}）の実行を推奨します。"
                                context["plan"]["confirmation_needed"] = True
                    
                    if len(impacted_methods) > 3 and not context["plan"].get("suggested_tests"):
                        context["plan"]["suggestion"] = f"修正対象 '{target_name}' は {len(impacted_methods)} 個のメソッドに影響します。広範囲のテスト実行を推奨します。"
                        context["plan"]["confirmation_needed"] = True # Force confirmation for high impact
        except Exception as e:
            self.log_manager.log_event("planner_impact_analysis_error", {"error": str(e)}, level="WARN")
