import time
import unittest

from src.task_manager.metrics import TaskManagerMetrics


class TestTaskManagerMetrics(unittest.TestCase):
    def test_stale_task_is_completed_as_timeout(self):
        metrics = TaskManagerMetrics()
        metrics.start_task("session-1", "example")
        metrics.active_tasks["session-1"].start_time = time.time() - 7200

        cleaned = metrics.cleanup_stale_tasks(max_age_hours=1)

        self.assertEqual(cleaned, 1)
        self.assertNotIn("session-1", metrics.active_tasks)
        self.assertEqual(metrics.completed_tasks[-1].final_state, "TIMEOUT")
        self.assertTrue(metrics.completed_tasks[-1].is_completed)
