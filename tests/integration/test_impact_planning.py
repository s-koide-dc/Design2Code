# -*- coding: utf-8 -*-
"""C# analysis outputからPlannerの影響範囲・テスト提案までを検証する。"""

import unittest
from unittest.mock import patch
from pathlib import Path

from src.pipeline_core.pipeline_core import Pipeline


class TestImpactPlanning(unittest.TestCase):
    def setUp(self):
        # This scenario validates Roslyn output and planner wiring, not vector
        # retrieval. Keep it deterministic in asset-free CI and model-backed
        # local environments alike.
        with patch.dict("os.environ", {"SKIP_VECTOR_MODEL": "1"}):
            self.pipeline = Pipeline(is_test_mode=True)

    def test_project_analysis_feeds_impact_scope_and_test_suggestion(self):
        project_path = Path("tests/fixtures/GeneralityCheck/GeneralityCheck.csproj")
        analysis_context = {
            "session_id": "impact-planning-test",
            "analysis": {
                "entities": {
                    "filename": {
                        "value": project_path.as_posix(),
                        "confidence": 1.0,
                    }
                }
            },
            "errors": [],
        }
        analysis_context = self.pipeline.action_executor._analyze_csharp(
            analysis_context,
            {"filename": project_path.as_posix()},
        )

        self.assertIn("action_result", analysis_context, msg=analysis_context.get("errors", []))
        self.assertEqual("success", analysis_context["action_result"]["status"])
        self.assertEqual(
            project_path.as_posix(),
            analysis_context["analysis"]["entities"]["filename"]["value"],
        )
        output_path = analysis_context["analysis"]["entities"]["output_path"]["value"]

        planning_context = {
            "session_id": analysis_context["session_id"],
            "analysis": {"entities": analysis_context["analysis"]["entities"]},
            "plan": {},
        }
        self.pipeline.planner._refine_plan_with_impact_analysis(
            planning_context,
            {
                "output_path": output_path,
                "target_name": "DependencyDemo.ServiceB.GetData",
            },
        )

        plan = planning_context["plan"]
        self.assertIn("DependencyDemo.ServiceA.Process", plan["impacted_methods"])
        self.assertIn("DependencyDemo.Client.Run", plan["impacted_methods"])
        self.assertEqual("ServiceATests", plan["suggested_tests"][0]["test_class"].split(".")[-1])
        self.assertTrue(plan["confirmation_needed"])


if __name__ == "__main__":
    unittest.main()
