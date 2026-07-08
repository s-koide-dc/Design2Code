# -*- coding: utf-8 -*-
import unittest
import os
import shutil
import subprocess
import time
import uuid

from src.pipeline_core.pipeline_core import Pipeline

class TestPhase6MultiTurn(unittest.TestCase):
    def setUp(self):
        self.pipeline = Pipeline()
        self.pipeline.task_manager.config.debug_mode = True
        self.root_dir = os.getcwd()
        self.session_id = f"phase6_multi_turn_test_{uuid.uuid4().hex}"
        self.repro_dir = os.path.join(
            self.root_dir,
            "tests",
            f"repro_multi_turn_{self.session_id}",
        )
        self.backup_dir = os.path.join(self.root_dir, "backup")
        self.existing_backups = (
            set(os.listdir(self.backup_dir))
            if os.path.isdir(self.backup_dir)
            else set()
        )
        
        self._remove_repro_dir()
        os.makedirs(self.repro_dir)
        
        # Create SUT and Test files
        self._setup_repro_files()

    def _setup_repro_files(self):
        sut_content = """
namespace MultiTurnRepro
{
    public class DataItem { public string Value { get; set; } }
    public interface IDataService { DataItem GetData(int id); }
    public class Processor
    {
        private readonly IDataService _service;
        public Processor(IDataService service) { _service = service; }
        public int GetLength(int id) {
            var data = _service.GetData(id);
            return data.Value.Length; // NRE if data is null
        }
    }
}
"""
        test_content = """
using Xunit;
using NSubstitute;
using MultiTurnRepro;

public class ProcessorTests
{
    [Fact]
    public void GetLength_ShouldReturnLength_WhenDataExists()
    {
        var mock = Substitute.For<IDataService>();
        var sut = new Processor(mock);
        // Missing mock setup
        var result = sut.GetLength(1);
        Assert.Equal(4, result);
    }
}
"""
        csproj_content = """
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup><TargetFramework>net10.0</TargetFramework></PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.8.0" />
    <PackageReference Include="xunit" Version="2.6.1" />
    <PackageReference Include="xunit.runner.visualstudio" Version="2.5.3" />
    <PackageReference Include="NSubstitute" Version="5.1.0" />
  </ItemGroup>
</Project>
"""
        with open(os.path.join(self.repro_dir, "Processor.cs"), "w", encoding="utf-8") as f: f.write(sut_content)
        with open(os.path.join(self.repro_dir, "ProcessorTests.cs"), "w", encoding="utf-8") as f: f.write(test_content)
        with open(os.path.join(self.repro_dir, "Repro.csproj"), "w", encoding="utf-8") as f: f.write(csproj_content)

    def tearDown(self):
        self._remove_repro_dir()
        if os.path.isdir(self.backup_dir):
            for filename in set(os.listdir(self.backup_dir)) - self.existing_backups:
                backup_path = os.path.join(self.backup_dir, filename)
                if os.path.isfile(backup_path):
                    os.remove(backup_path)
            if not os.listdir(self.backup_dir):
                os.rmdir(self.backup_dir)

    def _remove_repro_dir(self):
        if not os.path.exists(self.repro_dir):
            return
        subprocess.run(
            ["dotnet", "build-server", "shutdown"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        for _ in range(5):
            try:
                shutil.rmtree(self.repro_dir)
                return
            except PermissionError:
                time.sleep(0.5)

    def test_phase6_multi_turn_flow(self):
        """Phase 6の複数ターンでの動作（テストArrangeの自動修正）を検証"""
        
        csproj_path = os.path.join(self.repro_dir, "Repro.csproj")
        
        # --- Turn 1: Run Test ---
        print("\n--- Turn 1: Run failing test ---")
        context1 = self.pipeline.run(f"session_id:{self.session_id} テストを実行して")
        if "action_result" not in context1:
            context1 = self.pipeline.run(
                f"session_id:{self.session_id} 対象は「{csproj_path}」です"
            )
        print(f"[DEBUG] Turn 1 action_result keys: {context1.get('action_result', {}).keys()}")
        if 'action_result' in context1 and 'test_summary' in context1['action_result']:
            details = context1['action_result']['test_summary'].get('error_details', [])
            if details:
                print(f"[DEBUG] Turn 1 Stack Trace:\n{details[0].get('stack_trace')}")
        self.assertEqual(context1["action_result"]["test_summary"]["failed_count"], 1)

        # --- Turn 2: Analyze Failure ---
        print("\n--- Turn 2: Analyze failure and get suggestion ---")
        context2 = self.pipeline.run(
            f"session_id:{self.session_id} 失敗したテストの原因を一括分析して"
        )
        
        if "analysis_result" not in context2["action_result"]:
            print(f"Turn 2 Failed: {context2['action_result'].get('message')}")
            self.fail("Turn 2 failed to produce analysis_result")

        analysis_result = context2["action_result"]["analysis_result"]
        failure_analysis = analysis_result["analyses"][0]
        suggestions = analysis_result["fix_suggestions"]
        
        self.assertEqual(failure_analysis["root_cause"], "missing_test_data")
        self.assertEqual(suggestions[0]["type"], "manual_fix")
        self.assertFalse(suggestions[0]["auto_applicable"])
        self.assertEqual(suggestions[0]["suggested_code"], "")
        self.assertEqual(
            suggestions[0]["impact_analysis"]["recommended_action"],
            "inspect_manual_fix",
        )
        print(f"Suggested Code: {suggestions[0]['suggested_code']}")

        with open(
            os.path.join(self.repro_dir, "ProcessorTests.cs"),
            encoding="utf-8",
        ) as test_file:
            unchanged_test = test_file.read()
        self.assertNotIn(
            "mock.GetData(",
            unchanged_test,
        )

if __name__ == "__main__":
    unittest.main()
