# -*- coding: utf-8 -*- 
# src/pipeline_core/pipeline_core.py

import os
import sys
import json
from datetime import datetime
from src.utils.context_utils import _get_context_summary

from src.morph_analyzer.morph_analyzer import MorphAnalyzer
from src.syntactic_analyzer.syntactic_analyzer import SyntacticAnalyzer
from src.semantic_analyzer.semantic_analyzer import SemanticAnalyzer
from src.response_generator.response_generator import ResponseGenerator
from src.intent_detector.intent_detector import IntentDetector
from src.vector_engine.vector_engine import VectorEngine
from src.action_executor.action_executor import ActionExecutor
from src.context_manager.context_manager import ContextManager
from src.clarification_manager.clarification_manager import ClarificationManager
from src.planner.planner import Planner
from src.log_manager.log_manager import LogManager
from src.task_manager.task_manager import TaskManager
from src.autonomous_learning.autonomous_learning import AutonomousLearning

from src.config.config_manager import ConfigManager
from src.pipeline_core.stages import (
    SetupStage, LanguageAnalysisStage, IntentDetectionStage,
    SemanticAnalysisStage, TaskManagementStage, ClarificationStage,
    ExecutionStage, ResponseStage
)

class Pipeline:
    def __init__(self, clarification_thresholds=None, planner_intent_threshold=None, is_test_mode=False):
        # 1. Initialize Configuration Manager
        self.config_manager = ConfigManager()
        force_vector = os.environ.get("FORCE_VECTOR_MODEL") == "1"
        test_mode = is_test_mode or os.environ.get("PYTEST_CURRENT_TEST") or "unittest" in sys.modules
        if test_mode and not force_vector:
            # Skip vector loading only when cache is not available
            model_path = self.config_manager.vector_model_path
            vocab_cache = model_path + ".v0.vocab.npy"
            matrix_cache = model_path + ".v0.matrix.npy"
            if not (os.path.exists(vocab_cache) and os.path.exists(matrix_cache)):
                os.environ["SKIP_VECTOR_MODEL"] = "1"

        self._vector_engine = None
        self._vector_engine_future = None
        self._intent_detector = None
        self._response_generator = None
        self._autonomous_learning = None
        
        # 2. Setup Analyzers and Managers with injected config
        self.morph_analyzer = MorphAnalyzer(config_manager=self.config_manager)
        self.syntactic_analyzer = SyntacticAnalyzer()
        self.context_manager = ContextManager()
        self.log_manager = LogManager(config_manager=self.config_manager)
        
        # --- NEW: Maintenance ---
        try:
            from scripts.rotate_logs import rotate_logs
            rotate_logs()
        except: pass
        # ------------------------

        # Start background loading of VectorEngine using paths from config
        self._start_vector_engine_loading()

        self.action_executor = ActionExecutor(
            log_manager=self.log_manager,
            autonomous_learning=self.autonomous_learning,
            morph_analyzer=self.morph_analyzer,
            config_manager=self.config_manager
        ) 
        self.task_manager = TaskManager(
            action_executor=self.action_executor, 
            log_manager=self.log_manager,
            config_manager=self.config_manager
        )
        
        self.semantic_analyzer = SemanticAnalyzer(
            task_manager=self.task_manager, 
            config_manager=self.config_manager
        )
        self.semantic_analyzer.log_manager = self.log_manager # Injection
        self.action_executor.semantic_analyzer = self.semantic_analyzer
        
        c_config = self.config_manager.get_section("clarification")
        _clarification_thresholds = clarification_thresholds or {
            "intent": c_config.get("intent_threshold", 0.75),
            "entity": c_config.get("entity_threshold", 0.75)
        }
        self.clarification_manager = ClarificationManager(
            action_executor=self.action_executor, 
            log_manager=self.log_manager,
            clarification_thresholds=_clarification_thresholds
        )
        
        p_config = self.config_manager.get_section("planner")
        _planner_intent_threshold = planner_intent_threshold if planner_intent_threshold is not None else p_config.get("intent_threshold", 0.8)
        self.planner = Planner(
            action_executor=self.action_executor, 
            log_manager=self.log_manager,
            autonomous_learning=self.autonomous_learning,
            intent_entity_thresholds={"intent": _planner_intent_threshold, "entity": _clarification_thresholds["entity"]},
            config_manager=self.config_manager
        )

        # Initialize Pipeline Stages
        self.stages = [
            SetupStage(),
            LanguageAnalysisStage(),
            IntentDetectionStage(),
            SemanticAnalysisStage(),
            TaskManagementStage(),
            ClarificationStage(),
            ExecutionStage(),
            ResponseStage()
        ]

    def _start_vector_engine_loading(self):
        """Starts loading VectorEngine in a background thread."""
        import concurrent.futures
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._vector_engine_future = executor.submit(VectorEngine, model_path=self.config_manager.vector_model_path)

    @property
    def vector_engine(self):
        if self._vector_engine is None:
            v_path = self.config_manager.vector_model_path
            if self._vector_engine_future:
                try:
                    # Wait for background loading to complete (with timeout)
                    self._vector_engine = self._vector_engine_future.result(timeout=30)
                except Exception as e:
                    self.log_manager.log_event("vector_engine_load_error", {"message": str(e)})
                    # Fallback to synchronous load if background failed
                    self._vector_engine = VectorEngine(model_path=v_path)
            else:
                self._vector_engine = VectorEngine(model_path=v_path)

            # Only set if action_executor already exists
            if hasattr(self, 'action_executor') and self.action_executor:
                self.action_executor.vector_engine = self._vector_engine
        return self._vector_engine

    @property
    def intent_detector(self):
        if self._intent_detector is None:
            self._intent_detector = IntentDetector(task_manager=self.task_manager) 
            self._intent_detector.set_vector_engine(self.vector_engine)
            self._intent_detector.prepare_corpus_vectors(self.morph_analyzer)
            if self._autonomous_learning: self._autonomous_learning.intent_detector = self._intent_detector
        return self._intent_detector

    @property
    def response_generator(self):
        if self._response_generator is None:
            self._response_generator = ResponseGenerator(vector_engine=self.vector_engine, log_manager=self.log_manager, task_manager=self.task_manager)
        return self._response_generator

    @property
    def autonomous_learning(self):
        if self._autonomous_learning is None:
            self._autonomous_learning = AutonomousLearning(
                workspace_root=os.getcwd(), 
                log_manager=self.log_manager, 
                intent_detector=self._intent_detector,
                vector_engine=self.vector_engine,
                morph_analyzer=self.morph_analyzer
            )
        return self._autonomous_learning
    
    def _log_and_return_error(self, session_id: str, message: str, level: str = "ERROR") -> dict:
        error_context = {
            "original_text": "", "session_id": session_id, "pipeline_history": [],
            "analysis": {"intent": "ERROR", "intent_confidence": 1.0},
            "errors": [{"module": "pipeline_core", "message": message}],
            "response": {"text": f"エラーが発生しました: {message}"}
        }
        self.log_manager.log_event("pipeline_error", {"message": message, "session_id": session_id}, level=level)
        self.context_manager.add_context(error_context)
        self.log_manager.log_event("pipeline_end", {"final_response": error_context["response"]["text"]}, level="INFO")
        self.autonomous_learning.trigger_learning(event_type="SESSION_COMPLETED", data=error_context)
        return error_context

    def _persist_session_log(self, context: dict, start_time: datetime):
        """Persists the events of the current turn to a JSON file for analytics."""
        events = self.log_manager.get_events_after(start_time)
        if not events: return
        
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        log_file = os.path.join(log_dir, f"pipeline_{timestamp}.json")
        
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                for event in events:
                    f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            self.log_manager.log_event("log_persistence_error", {"error": str(e)}, level="ERROR")

    def run(self, text: str) -> dict:
        start_time = datetime.now()
        context = {
            "original_text": text,
            "session_id": "default_session",
            "pipeline_history": [],
            "analysis": {},
            "errors": [],
            "response": {},
            "plan": None
        }

        for stage in self.stages:
            try:
                context = stage.execute(context, self)
                if context.get("_early_exit"): break
            except Exception as e:
                import traceback
                self.log_manager.log_event("pipeline_stage_error", {"stage": stage.__class__.__name__, "error": str(e), "traceback": traceback.format_exc()}, level="ERROR")
                error_ctx = self._log_and_return_error(context.get("session_id", "default_session"), f"Stage {stage.__class__.__name__} failed: {str(e)}")
                self._persist_session_log(error_ctx, start_time)
                return error_ctx

        self._persist_session_log(context, start_time)
        return context

if __name__ == '__main__':
    pipeline = Pipeline()
    while True:
        try:
            user_input = input("あなた: ")
            if user_input.lower() in ['exit', 'quit']: break
            final_context = pipeline.run(user_input)
            print(f"AI: {final_context.get('response', {}).get('text', 'N/A')}")
        except KeyboardInterrupt: break
        except Exception as e: print(f"AI: 予期せぬエラーが発生しました: {e}")
