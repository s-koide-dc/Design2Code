# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch

from src.pipeline_core.stages import ExecutionStage, SetupStage


class TestPipelineStageContracts(unittest.TestCase):
    def test_setup_stage_accepts_documented_input_limit(self):
        pipeline = MagicMock()
        context = {
            "original_text": "a" * (200 * 1024),
            "session_id": "default_session",
            "pipeline_history": [],
        }

        result = SetupStage().execute(context, pipeline)

        self.assertIs(result, context)
        self.assertEqual(result["session_id"], "default_session")
        pipeline._log_and_return_error.assert_not_called()

    def test_setup_stage_rejects_input_over_documented_limit(self):
        pipeline = MagicMock()
        error_context = {"errors": [{"module": "pipeline_core"}]}
        pipeline._log_and_return_error.return_value = error_context
        context = {
            "original_text": "a" * (200 * 1024 + 1),
            "session_id": "default_session",
            "pipeline_history": [],
        }

        result = SetupStage().execute(context, pipeline)

        self.assertIs(result, error_context)
        pipeline._log_and_return_error.assert_called_once()
        args = pipeline._log_and_return_error.call_args.args
        self.assertEqual(args[0], "default_session")
        self.assertIn("too long", args[1])

    def test_execution_stage_stops_after_documented_timeout(self):
        pipeline = MagicMock()
        session_id = "stage-contract-session"
        active_task = {"type": "COMPOUND_TASK", "state": "IN_PROGRESS"}
        pipeline.task_manager.active_tasks = {session_id: active_task}
        pipeline.task_manager.update_task_after_execution.side_effect = lambda context: context
        pipeline.task_manager.manage_task_state.side_effect = lambda context: context
        pipeline.planner.create_plan.side_effect = lambda context: {
            **context,
            "plan": {"action_method": "test_action"},
        }
        pipeline.action_executor.execute.side_effect = lambda context: {
            **context,
            "action_result": {"status": "success"},
        }
        context = {
            "session_id": session_id,
            "analysis": {"intent": "TEST_ACTION"},
            "history": [],
            "response": {},
            "errors": [],
            "plan": None,
        }

        with patch("src.pipeline_core.stages.time.time", side_effect=[0, 0, 61]):
            result = ExecutionStage().execute(context, pipeline)

        self.assertIn("時間がかかりすぎた", result["response"]["text"])
        pipeline.action_executor.execute.assert_called_once()

    def test_execution_stage_stops_after_documented_iteration_limit(self):
        pipeline = MagicMock()
        session_id = "iteration-contract-session"
        active_task = {"type": "COMPOUND_TASK", "state": "IN_PROGRESS"}
        pipeline.task_manager.active_tasks = {session_id: active_task}
        pipeline.task_manager.update_task_after_execution.side_effect = lambda context: context
        pipeline.task_manager.manage_task_state.side_effect = lambda context: context
        pipeline.planner.create_plan.side_effect = lambda context: {
            **context,
            "plan": {"action_method": "test_action"},
        }
        pipeline.action_executor.execute.side_effect = lambda context: {
            **context,
            "action_result": {"status": "success"},
        }
        context = {
            "session_id": session_id,
            "analysis": {"intent": "TEST_ACTION"},
            "history": [],
            "response": {},
            "errors": [],
            "plan": None,
        }

        with patch("src.pipeline_core.stages.time.time", return_value=0):
            result = ExecutionStage().execute(context, pipeline)

        self.assertIn("上限に達しました", result["response"]["text"])
        self.assertEqual(pipeline.action_executor.execute.call_count, 10)


if __name__ == "__main__":
    unittest.main()
