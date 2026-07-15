import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.action_executor.action_executor import ActionExecutor
from src.code_verification.dependency_contract import (
    InvalidDependencyError,
    render_package_references,
)
from src.config.config_manager import ConfigManager
from src.log_manager.log_manager import LogManager
from src.pipeline_core.pipeline_core import Pipeline
from src.task_manager.task_persistence import TaskPersistence


class TestWorkspaceBoundaries(unittest.TestCase):
    def test_command_runs_in_configured_workspace(self):
        with tempfile.TemporaryDirectory() as workspace:
            executor = ActionExecutor(
                LogManager(log_dir=os.path.join(workspace, "logs")),
                workspace_root=workspace,
            )
            completed = subprocess.CompletedProcess(["echo", "ok"], 0, "ok\n", "")
            with patch("src.action_executor.action_executor.subprocess.run", return_value=completed) as run:
                result = executor.execute({
                    "plan": {
                        "action_method": "_run_command",
                        "parameters": {"command": "echo ok"},
                    }
                })

            self.assertEqual(result["action_result"]["status"], "success")
            self.assertEqual(run.call_args.kwargs["cwd"], workspace)

    def test_task_state_ids_do_not_collide(self):
        with tempfile.TemporaryDirectory() as storage:
            persistence = TaskPersistence(storage_dir=storage)
            first = persistence._get_state_file_path("a/b")
            second = persistence._get_state_file_path("ab")
            self.assertNotEqual(first, second)
            self.assertTrue(persistence.save_task_state("a/b", {"value": 1}))
            self.assertTrue(persistence.save_task_state("ab", {"value": 2}))
            self.assertEqual(persistence.load_task_state("a/b"), {"value": 1})
            self.assertEqual(persistence.load_task_state("ab"), {"value": 2})
            self.assertEqual(list(Path(storage).glob("*.tmp")), [])

    def test_dependency_contract_rejects_xml_injection(self):
        with self.assertRaises(InvalidDependencyError):
            render_package_references([{"name": "Safe", "version": '1.0" />\n<Exec Command="bad"'}])

    def test_config_manager_resolves_workspace_root(self):
        manager = ConfigManager(workspace_root=".")
        self.assertEqual(manager.workspace_root, Path.cwd().resolve())

    def test_pipeline_skipped_vector_model_avoids_background_loader(self):
        with patch.dict(os.environ, {"SKIP_VECTOR_MODEL": "1"}), \
                patch("src.pipeline_core.pipeline_core.VectorEngine") as vector_engine:
            Pipeline(is_test_mode=True)

        vector_engine.assert_called_once()
        self.assertTrue(vector_engine.call_args.kwargs["skip_load"])


if __name__ == "__main__":
    unittest.main()
