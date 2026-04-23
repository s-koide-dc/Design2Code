# -*- coding: utf-8 -*-
# src/pipeline_core/stages.py

from abc import ABC, abstractmethod
import time
import os
from src.utils.context_utils import _get_context_summary

class PipelineStage(ABC):
    @abstractmethod
    def execute(self, context: dict, pipeline: 'Pipeline') -> dict:
        pass

class SetupStage(PipelineStage):
    def execute(self, context: dict, pipeline: 'Pipeline') -> dict:
        text = context.get("original_text", "")
        
        # 1. Input Length Validation
        MAX_INPUT_LENGTH = 200 * 1024 # 200KB
        if len(text) > MAX_INPUT_LENGTH:
             return pipeline._log_and_return_error("default_session", f"Input text too long ({len(text)} bytes)")

        # 2. Session ID Extraction
        session_id, remaining = _extract_session_id(text)
        if session_id:
            text = remaining
            context["original_text"] = text
        else:
            session_id = context.get("session_id", "default_session")
        
        context["session_id"] = session_id
        pipeline.log_manager.log_event("pipeline_start", {"original_text": text, "session_id": session_id}, level="INFO")

        # 3. Feedback Collection
        if pipeline.context_manager.is_awaiting_feedback(session_id):
            pipeline.context_manager.set_awaiting_feedback(session_id, False)
            pipeline.autonomous_learning.record_user_feedback(finding_id=session_id, feedback=text)
            context["pipeline_history"].append("feedback_collection")
            context["analysis"] = {"intent": "FEEDBACK_RECEIVED"}
            context["response"] = {"text": "ありがとうございます。フィードバックを記録し、学習しました。"}
            context["_early_exit"] = True
            return context

        context["plan"] = None
        return context

def _extract_session_id(text: str) -> tuple[str | None, str]:
    if not text:
        return None, text
    prefix = "session_id:"
    if not text.startswith(prefix):
        return None, text
    rest = text[len(prefix):].lstrip()
    if not rest:
        return None, text
    # session id ends at first whitespace
    i = 0
    while i < len(rest) and not rest[i].isspace():
        i += 1
    sid = rest[:i]
    remaining = rest[i:].lstrip()
    return sid, remaining

class LanguageAnalysisStage(PipelineStage):
    def execute(self, context: dict, pipeline: 'Pipeline') -> dict:
        if context.get("_early_exit"): return context
        
        context = pipeline.morph_analyzer.analyze(context)
        pipeline.log_manager.log_event("pipeline_stage_completion", {"stage": "morph_analysis", "context_summary": _get_context_summary(context)}, level="DEBUG")
        
        context = pipeline.syntactic_analyzer.analyze(context)
        pipeline.log_manager.log_event("pipeline_stage_completion", {"stage": "syntactic_analysis", "context_summary": _get_context_summary(context)}, level="DEBUG")
        
        session_id = pipeline.task_manager.get_session_id(context)
        context["session_id"] = session_id
        return context

class IntentDetectionStage(PipelineStage):
    def execute(self, context: dict, pipeline: 'Pipeline') -> dict:
        if context.get("_early_exit"): return context
        
        session_id = context["session_id"]
        current_task = pipeline.task_manager.active_tasks.get(session_id)
        if current_task: context["task"] = current_task
        
        context = pipeline.intent_detector.detect(context)
        pipeline.log_manager.log_event("pipeline_stage_completion", {"stage": "intent_detection", "context_summary": _get_context_summary(context)}, level="INFO")
        
        current_intent = context["analysis"].get("intent")

        if current_intent == "CORRECTION":
            pipeline.context_manager.set_awaiting_feedback(session_id, True)
            context["response"]["text"] = "申し訳ありません。どのように間違っていましたか？（正解や理由を教えてください）"
            context["_early_exit"] = True
            return context

        # Confirmation Shortcut
        pending_plan = pipeline.context_manager.get_pending_confirmation_plan(session_id)
        if pending_plan and current_intent == "AGREE":
            context["plan"] = pending_plan
            context["plan"]["confirmation_needed"] = False
            context["confirmation_granted"] = True
            pipeline.context_manager.clear_pending_confirmation_plan(session_id)
            context["_skip_initial_pipeline_steps"] = True
        elif pending_plan and current_intent == "DISAGREE":
            pipeline.context_manager.clear_pending_confirmation_plan(session_id)
            context["response"]["text"] = "アクションはキャンセルされました。"
            context["_early_exit"] = True
            return context

        return context

class SemanticAnalysisStage(PipelineStage):
    def execute(self, context: dict, pipeline: 'Pipeline') -> dict:
        if context.get("_early_exit"): return context
        
        session_id = context["session_id"]
        context["history"] = pipeline.context_manager.get_history(session_id)
        
        if not context.get("_skip_initial_pipeline_steps", False):
            context = pipeline.semantic_analyzer.analyze(context)
            pipeline.log_manager.log_event("pipeline_stage_completion", {"stage": "semantic_analysis", "context_summary": _get_context_summary(context)}, level="DEBUG")

        # Healing Mode Detection
        has_recent_error = False
        if context["history"] and context["history"][-1].get("action_result", {}).get("status") == "error":
            has_recent_error = True
        
        context["_is_healing_mode"] = has_recent_error
        
        return context

class TaskManagementStage(PipelineStage):
    def execute(self, context: dict, pipeline: 'Pipeline') -> dict:
        if context.get("_early_exit"): return context
        
        if not context.get("_skip_initial_pipeline_steps", False) and not context.get("_is_healing_mode"):
            context = pipeline.task_manager.manage_task_state(context)
            
            conversational_intents = ["GREETING", "PERSONAL_Q", "EMOTIVE", "SMALLTALK", "FEEDBACK", "WEATHER", "TIME", "CAPABILITY", "BYE", "DEFINITION", "GENERAL"]
            current_intent = context["analysis"].get("intent")
            if current_intent in conversational_intents and context.get("task_interruption"):
                context = pipeline.response_generator.generate(context)
                pipeline.log_manager.log_event("pipeline_stage_completion", {"stage": "response_generation", "context_summary": _get_context_summary(context)}, level="DEBUG")
                context["_early_exit"] = True
        
        return context

class ClarificationStage(PipelineStage):
    def execute(self, context: dict, pipeline: 'Pipeline') -> dict:
        if context.get("_early_exit"): return context
        
        if not context.get("_skip_initial_pipeline_steps", False) and not context.get("_is_healing_mode"):
            context = pipeline.clarification_manager.manage_clarification(context)
            pipeline.log_manager.log_event("pipeline_stage_completion", {"stage": "clarification_management", "context_summary": _get_context_summary(context)}, level="INFO")
        
        if context.get("clarification_needed") and not context.get("_is_healing_mode"):
            current_intent = context["analysis"].get("intent")
            is_conversational = current_intent in ["GREETING", "PERSONAL_Q", "EMOTIVE", "SMALLTALK", "FEEDBACK", "WEATHER", "TIME", "CAPABILITY", "BYE", "DEFINITION", "GENERAL"]
            
            if not context.get("response", {}).get("text"):
                context = pipeline.response_generator.generate(context)
                pipeline.log_manager.log_event("pipeline_stage_completion", {"stage": "response_generation", "context_summary": _get_context_summary(context)}, level="DEBUG")
            
            # If it's NOT a simple conversational intent, exit early.
            # For DEFINITION/GENERAL, we want to proceed to ResponseStage to finalize.
            if not is_conversational:
                context["_early_exit"] = True
            
        return context

class ExecutionStage(PipelineStage):
    def execute(self, context: dict, pipeline: 'Pipeline') -> dict:
        if context.get("_early_exit"): return context
        
        current_intent = context["analysis"].get("intent")
        is_conversational = current_intent in ["GREETING", "PERSONAL_Q", "EMOTIVE", "SMALLTALK", "FEEDBACK", "WEATHER", "TIME", "CAPABILITY", "BYE", "DEFINITION", "GENERAL"]
        if is_conversational:
            return context

        session_id = context["session_id"]
        MAX_ITERATIONS = 10
        iteration_count = 0
        start_time = time.time()
        LOOP_TIMEOUT = 60 # 60 seconds total for execution loop

        while iteration_count < MAX_ITERATIONS:
            if time.time() - start_time > LOOP_TIMEOUT:
                pipeline.log_manager.log_event("pipeline_loop_timeout", {"session_id": session_id})
                context["response"]["text"] = "処理に時間がかかりすぎたため、中断しました。現在の状況を確認してください。"
                break

            iteration_count += 1
            # Clear critical safety errors from previous turns before planning a NEW action
            if not context.get("plan"):
                context["errors"] = [e for e in context.get("errors", []) if "Safety Policy Error" not in e.get("message", "")]

            if not context.get("plan"):
                context = pipeline.planner.create_plan(context)
                pipeline.log_manager.log_event("pipeline_stage_completion", {"stage": "plan_creation", "context_summary": _get_context_summary(context)}, level="INFO")
                
                # Automated Recovery Task Promotion
                plan = context.get("plan", {})
                if plan and plan.get("healing_type") in ["KNOWLEDGE_BASE_RECOVERY", "RETRY_RULE_MATCH"]:
                    current_task = pipeline.task_manager.active_tasks.get(session_id)
                    if not current_task or current_task["name"] != "RECOVERY_FROM_TEST_FAILURE":
                        if pipeline.task_manager.is_recovery_limit_reached(session_id):
                            pipeline.log_manager.log_event("pipeline_recovery_limit_reached", {"session_id": session_id}, level="WARN")
                            context["response"]["text"] = "自律修復を数回試みましたが、問題が解決しませんでした。状況を整理しますので、手動での確認をお願いします。"
                            context["clarification_needed"] = True
                            context["_early_exit"] = True
                            return context
                        
                        context = pipeline.task_manager.create_recovery_task(session_id, context)

                if context.get("errors"):
                    if not context.get("response", {}).get("text"):
                        context = pipeline.response_generator.generate(context)
                        pipeline.log_manager.log_event("pipeline_stage_completion", {"stage": "response_generation", "context_summary": _get_context_summary(context)}, level="DEBUG")
                    context["_early_exit"] = True
                    return context
            
            if context.get("clarification_needed") and not context.get("plan"): 
                context["_early_exit"] = True
                break
            
            if context.get("plan", {}).get("confirmation_needed"):
                pipeline.context_manager.set_pending_confirmation_plan(context["plan"], session_id)
                context = pipeline.response_generator.generate_confirmation_message(context)
                context["clarification_needed"] = True
                # Redundant log removed to avoid test confusion if multiple modules log this
                # pipeline.log_manager.log_event("clarification_needed", {"message": context.get("response", {}).get("text")}, level="INFO")
                context["_early_exit"] = True
                break 
            
            if not context.get("plan"): break

            # Execute
            context = pipeline.action_executor.execute(context)
            pipeline.log_manager.log_event("pipeline_stage_completion", {"stage": "action_execution", "context_summary": _get_context_summary(context)}, level="INFO")
            context = pipeline.task_manager.update_task_after_execution(context)

            # Chained Task Loop
            current_task = pipeline.task_manager.active_tasks.get(session_id)
            if current_task and current_task.get("type") == "COMPOUND_TASK" and current_task.get("state") == "IN_PROGRESS":
                context['plan'] = None
                context['action_result'] = {}
                context = pipeline.task_manager.manage_task_state(context)
                if context.get("clarification_needed"): 
                    context["_early_exit"] = True
                    break
                else: continue 
            else: break
        
        if iteration_count >= MAX_ITERATIONS and not context.get("response", {}).get("text"):
             pipeline.log_manager.log_event("pipeline_max_iterations", {"session_id": session_id})
             context["response"]["text"] = "タスクの実行ステップ数が上限に達しました。安全のため一旦停止します。"

        return context

class ResponseStage(PipelineStage):
    def execute(self, context: dict, pipeline: 'Pipeline') -> dict:
        if not context.get("response", {}).get("text"):
             context = pipeline.response_generator.generate(context)
             pipeline.log_manager.log_event("pipeline_stage_completion", {"stage": "response_generation", "context_summary": _get_context_summary(context)}, level="DEBUG")
        
        pipeline.log_manager.log_event("pipeline_end", {"final_response": context.get("response", {}).get("text")}, level="INFO")
        pipeline.context_manager.add_context(context)
        pipeline.autonomous_learning.trigger_learning(event_type="SESSION_COMPLETED", data=context)
        return context
