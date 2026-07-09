# -*- coding: utf-8 -*-
import unittest
import os
import shutil
from src.pipeline_core.pipeline_core import Pipeline
from src.context_manager.context_manager import ContextManager


class TestContextManagerUnit(unittest.TestCase):
    def test_history_is_trimmed_on_add_and_clear_pending_plan(self):
        manager = ContextManager(max_history=2)
        for index in range(3):
            manager.add_context({
                "session_id": "s1",
                "original_text": f"turn {index}",
                "analysis": {"intent": f"INTENT_{index}"},
            })

        self.assertEqual(
            ["turn 1", "turn 2"],
            [entry["original_text"] for entry in manager.get_history("s1")],
        )

        manager.set_pending_confirmation_plan({"id": "plan"}, "s1")
        manager.clear_pending_confirmation_plan("s1")

        self.assertFalse(manager.has_pending_confirmation_plan("s1"))
        self.assertEqual(2, len(manager.get_history("s1")))

class TestContextAndAnaphora(unittest.TestCase):
    def setUp(self):
        self.pipeline = Pipeline()
        self.test_workspace = os.path.abspath("test_context_ws")
        if not os.path.exists(self.test_workspace):
            os.makedirs(self.test_workspace)
        self.pipeline.action_executor.workspace_root = self.test_workspace

    def tearDown(self):
        if os.path.exists(self.test_workspace):
            shutil.rmtree(self.test_workspace)

    def test_anaphora_resolution_flow(self):
        # Arrange the prior completed turn directly so this test isolates
        # contextual entity resolution from intent-model availability.
        with open(os.path.join(self.test_workspace, "memo.txt"), "w", encoding="utf-8") as file:
            file.write("これはメモです")
        self.pipeline.context_manager.add_context({
            "session_id": "default_session",
            "original_text": "memo.txt を作成",
            "analysis": {
                "intent": "FILE_CREATE",
                "entities": {"filename": {"value": "memo.txt", "confidence": 0.9}},
            },
            "action_result": {"status": "success"},
        })

        # Read "it" (anaphora resolution)
        result = self.pipeline.run("それを読み込んで")

        intent = result["analysis"]["intent"]
        entities = result["analysis"]["entities"]

        self.assertEqual(entities.get("filename").get("value"), "memo.txt") # Access value of entity
        self.assertEqual(intent, "FILE_READ") # Expecting FILE_READ after anaphora resolution
        self.assertEqual(result["action_result"]["status"], "success")
        self.assertIn("これはメモです", result["action_result"]["message"]) # Assert content is read

    def test_history_persistence(self):
        self.pipeline.run("こんにちは")
        self.pipeline.run("元気？")

        history = self.pipeline.context_manager.get_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["intent"], "GREETING")

if __name__ == "__main__":
    unittest.main()
