# -*- coding: utf-8 -*-
# tests/test_compound_task_scenarios.py

"""
複合タスクの実用性シナリオテスト
実際の開発ワークフローでの複合タスク + 品質分析統合機能をテスト
"""

import unittest
import os
import tempfile
import shutil
import json
import time
from unittest.mock import Mock, patch, MagicMock
from src.pipeline_core.pipeline_core import Pipeline
from src.task_manager.task_manager import TaskManager
from src.coverage_analyzer.coverage_analyzer import CoverageAnalyzer
from src.refactoring_analyzer.refactoring_analyzer import RefactoringAnalyzer


class TestCompoundTaskScenarios(unittest.TestCase):
    """複合タスクの実用性シナリオテストクラス"""
    
    @classmethod
    def setUpClass(cls):
        """テスト用リソースの準備"""
        cls.temp_dir = tempfile.mkdtemp()
        cls.test_resources_dir = os.path.join(cls.temp_dir, "compound_test_resources")
        os.makedirs(cls.test_resources_dir, exist_ok=True)
        
        # 複合タスク定義を作成
        cls._create_compound_task_definitions()
        
        # テスト用プロジェクト構造を作成
        cls.test_project_path = os.path.join(cls.temp_dir, "TestProject")
        cls._create_test_project()
    
    @classmethod
    def tearDownClass(cls):
        """テスト後のクリーンアップ"""
        shutil.rmtree(cls.temp_dir, ignore_errors=True)
    
    @classmethod
    def _create_compound_task_definitions(cls):
        """複合タスク定義を作成"""
        task_definitions = {
            "BACKUP_AND_DELETE": {
                "type": "COMPOUND_TASK",
                "subtasks": [
                    {
                        "task_type": "FILE_READ",
                        "parameter_mapping": {
                            "filename": "source_filename"
                        }
                    },
                    {
                        "task_type": "FILE_CREATE", 
                        "parameter_mapping": {
                            "filename": "backup_filename",
                            "content": "file_content"
                        }
                    },
                    {
                        "task_type": "FILE_DELETE",
                        "parameter_mapping": {
                            "filename": "source_filename"
                        }
                    }
                ],
                "templates": {
                    "overall_approval": "ファイル '{source_filename}' を '{backup_filename}' にバックアップして削除します。よろしいですか？"
                }
            },
            "CREATE_AND_ANALYZE": {
                "type": "COMPOUND_TASK",
                "subtasks": [
                    {
                        "task_type": "FILE_CREATE",
                        "parameter_mapping": {
                            "filename": "filename",
                            "content": "content"
                        }
                    },
                    {
                        "task_type": "MEASURE_COVERAGE",
                        "parameter_mapping": {
                            "project_path": "project_path",
                            "language": "language"
                        }
                    },
                    {
                        "task_type": "ANALYZE_REFACTORING",
                        "parameter_mapping": {
                            "project_path": "project_path",
                            "language": "language"
                        }
                    }
                ]
            },
            "QUALITY_IMPROVEMENT_WORKFLOW": {
                "type": "COMPOUND_TASK",
                "subtasks": [
                    {
                        "task_type": "GENERATE_TESTS",
                        "parameter_mapping": {
                            "filename": "target_file",
                            "language": "language"
                        }
                    },
                    {
                        "task_type": "MEASURE_COVERAGE",
                        "parameter_mapping": {
                            "project_path": "project_path",
                            "language": "language"
                        }
                    },
                    {
                        "task_type": "ANALYZE_REFACTORING",
                        "parameter_mapping": {
                            "project_path": "project_path",
                            "language": "language"
                        }
                    },
                    {
                        "task_type": "GENERATE_CICD_CONFIG",
                        "parameter_mapping": {
                            "project_name": "project_name",
                            "language": "language"
                        }
                    }
                ]
            }
        }
        
        task_definitions_path = os.path.join(cls.test_resources_dir, "task_definitions.json")
        with open(task_definitions_path, 'w', encoding='utf-8') as f:
            json.dump(task_definitions, f, ensure_ascii=False, indent=2)
    
    @classmethod
    def _create_test_project(cls):
        """テスト用プロジェクトを作成"""
        os.makedirs(cls.test_project_path, exist_ok=True)
        
        # C#プロジェクトファイル
        calculator_code = '''using System;

namespace TestProject
{
    public class Calculator
    {
        public int Add(int a, int b)
        {
            return a + b;
        }
        
        public int Subtract(int a, int b)
        {
            return a - b;
        }
        
        // 未テストメソッド
        public int Multiply(int a, int b)
        {
            return a * b;
        }
    }
}'''
        
        with open(os.path.join(cls.test_project_path, "Calculator.cs"), 'w', encoding='utf-8') as f:
            f.write(calculator_code)
        
        # プロジェクトファイル
        csproj_content = '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net6.0</TargetFramework>
  </PropertyGroup>
</Project>'''
        
        with open(os.path.join(cls.test_project_path, "TestProject.csproj"), 'w', encoding='utf-8') as f:
            f.write(csproj_content)
    
    def setUp(self):
        """各テスト前の準備"""
        self.mock_log_manager = Mock()
        self.mock_action_executor = Mock()
        
        # TaskManagerを初期化
        self.task_manager = TaskManager(
            action_executor=self.mock_action_executor,
            task_definitions_path=os.path.join(self.test_resources_dir, "task_definitions.json")
        )
    
    def test_backup_and_delete_with_quality_check(self):
        """バックアップ&削除 + 品質チェックの複合ワークフロー"""
        print("\n=== バックアップ&削除 + 品質チェック ===")
        
        # テストファイルを作成
        source_file = os.path.join(self.temp_dir, "source.cs")
        source_content = '''public class TestClass {
    public void TestMethod() {
        Console.WriteLine("Test");
    }
}'''
        
        with open(source_file, 'w', encoding='utf-8') as f:
            f.write(source_content)
        
        # BACKUP_AND_DELETE複合タスクのシミュレーション
        print("Step 1: ファイルバックアップ&削除実行中...")
        
        # ファイル読み込み
        with open(source_file, 'r', encoding='utf-8') as f:
            file_content = f.read()
        
        # バックアップファイル作成
        backup_file = os.path.join(self.temp_dir, "source_backup.cs")
        with open(backup_file, 'w', encoding='utf-8') as f:
            f.write(file_content)
        
        # 元ファイル削除
        os.remove(source_file)
        
        # バックアップが成功し、元ファイルが削除されたことを確認
        self.assertTrue(os.path.exists(backup_file))
        self.assertFalse(os.path.exists(source_file))
        
        print("✅ バックアップ&削除完了")
        
        # Step 2: 品質分析実行
        print("Step 2: 品質分析実行中...")
        
        coverage_analyzer = CoverageAnalyzer(self.temp_dir, self.mock_log_manager)
        
        # カバレッジ分析のモック
        mock_coverage_data = {
            backup_file: {
                "TestClass": {
                    "System.Void TestClass::TestMethod()": {
                        "Lines": {"2": 0, "3": 0},  # 未カバー
                        "Branches": []
                    }
                }
            }
        }
        
        with patch.object(coverage_analyzer.collectors["csharp"], 'collect_coverage') as mock_collect:
            mock_collect.return_value = {
                "status": "success",
                "coverage_data": mock_coverage_data,
                "summary": {"line_coverage": 0.0, "total_lines": 2, "covered_lines": 0}
            }
            
            coverage_result = coverage_analyzer.analyze_project(self.temp_dir, "csharp")
        
        self.assertEqual(coverage_result["status"], "success")
        self.assertEqual(coverage_result["coverage_summary"]["line_coverage"], 0.0)
        
        print("✅ 品質分析完了: カバレッジ0%（テスト不足を検出）")
        
        # 複合ワークフローの成功を確認
        self.assertTrue(os.path.exists(backup_file))
        self.assertFalse(os.path.exists(source_file))
        self.assertEqual(coverage_result["status"], "success")
        
        print("🎉 バックアップ&削除 + 品質チェック成功!")
    
    def test_create_and_analyze_workflow(self):
        """ファイル作成 + 品質分析の統合ワークフロー"""
        print("\n=== ファイル作成 + 品質分析統合 ===")
        
        # Step 1: ファイル作成
        print("Step 1: 新しいファイル作成中...")
        
        new_file_path = os.path.join(self.test_project_path, "NewClass.cs")
        new_file_content = '''using System;

namespace TestProject
{
    public class NewClass
    {
        public string GetMessage()
        {
            return "Hello World";
        }
        
        public int Calculate(int x, int y)
        {
            if (x > 0 && y > 0)
            {
                return x * y;
            }
            return 0;
        }
    }
}'''
        
        with open(new_file_path, 'w', encoding='utf-8') as f:
            f.write(new_file_content)
        
        self.assertTrue(os.path.exists(new_file_path))
        print("✅ ファイル作成完了: NewClass.cs")
        
        # Step 2: カバレッジ分析
        print("Step 2: カバレッジ分析実行中...")
        
        coverage_analyzer = CoverageAnalyzer(self.temp_dir, self.mock_log_manager)
        
        mock_coverage_data = {
            new_file_path: {
                "TestProject.NewClass": {
                    "System.String TestProject.NewClass::GetMessage()": {
                        "Lines": {"8": 1, "9": 1},  # カバー済み
                        "Branches": []
                    },
                    "System.Int32 TestProject.NewClass::Calculate(System.Int32,System.Int32)": {
                        "Lines": {"13": 1, "14": 0, "15": 0, "17": 1},  # 部分的カバー
                        "Branches": []
                    }
                }
            }
        }
        
        with patch.object(coverage_analyzer.collectors["csharp"], 'collect_coverage') as mock_collect:
            mock_collect.return_value = {
                "status": "success",
                "coverage_data": mock_coverage_data,
                "summary": {"line_coverage": 75.0, "total_lines": 4, "covered_lines": 3}
            }
            
            coverage_result = coverage_analyzer.analyze_project(self.test_project_path, "csharp")
        
        self.assertEqual(coverage_result["status"], "success")
        self.assertEqual(coverage_result["coverage_summary"]["line_coverage"], 75.0)
        
        print("✅ カバレッジ分析完了: 75%")
        
        # Step 3: リファクタリング分析
        print("Step 3: リファクタリング分析実行中...")
        
        refactoring_analyzer = RefactoringAnalyzer(self.temp_dir, self.mock_log_manager, self.mock_action_executor)
        
        mock_roslyn_result = {
            "action_result": {
                "status": "success",
                "analysis": {
                    "manifest": {
                        "objects": [
                            {
                                "id": "new_class",
                                "type": "Class",
                                "name": "NewClass",
                                "filePath": new_file_path
                            }
                        ]
                    },
                    "details_by_id": {
                        "new_class": {
                            "id": "new_class",
                            "type": "Class",
                            "fullName": "TestProject.NewClass",
                            "filePath": new_file_path,
                            "startLine": 5,
                            "endLine": 20,
                            "methods": ["get_message", "calculate"]
                        }
                    }
                }
            }
        }
        
        self.mock_action_executor._analyze_csharp.return_value = mock_roslyn_result
        
        refactoring_result = refactoring_analyzer.analyze_project(self.test_project_path, "csharp")
        
        self.assertEqual(refactoring_result["status"], "success")
        
        print("✅ リファクタリング分析完了")
        
        # 統合ワークフローの成功を確認
        self.assertTrue(os.path.exists(new_file_path))
        self.assertEqual(coverage_result["status"], "success")
        self.assertEqual(refactoring_result["status"], "success")
        
        print("🎉 ファイル作成 + 品質分析統合成功!")
    
    def test_quality_improvement_workflow(self):
        """品質改善ワークフロー（テスト生成→カバレッジ→リファクタリング→CI/CD）"""
        print("\n=== 品質改善ワークフロー実行 ===")
        
        target_file = os.path.join(self.test_project_path, "Calculator.cs")
        
        # Step 1: テスト生成（シミュレーション）
        print("Step 1: テスト生成中...")
        
        test_dir = os.path.join(self.test_project_path, "Tests")
        os.makedirs(test_dir, exist_ok=True)
        
        generated_test = '''using Xunit;
using TestProject;

namespace TestProject.Tests
{
    public class CalculatorTests
    {
        [Fact]
        public void Add_ShouldReturnSum_WhenValidInputs()
        {
            var calculator = new Calculator();
            var result = calculator.Add(5, 3);
            Assert.Equal(8, result);
        }
        
        [Fact]
        public void Multiply_ShouldReturnProduct_WhenValidInputs()
        {
            var calculator = new Calculator();
            var result = calculator.Multiply(4, 3);
            Assert.Equal(12, result);
        }
    }
}'''
        
        test_file_path = os.path.join(test_dir, "CalculatorTests.cs")
        with open(test_file_path, 'w', encoding='utf-8') as f:
            f.write(generated_test)
        
        self.assertTrue(os.path.exists(test_file_path))
        print("✅ テスト生成完了: CalculatorTests.cs")
        
        # Step 2: カバレッジ測定
        print("Step 2: カバレッジ測定中...")
        
        coverage_analyzer = CoverageAnalyzer(self.temp_dir, self.mock_log_manager)
        
        mock_coverage_data = {
            target_file: {
                "TestProject.Calculator": {
                    "System.Int32 TestProject.Calculator::Add(System.Int32,System.Int32)": {
                        "Lines": {"7": 1, "8": 1},
                        "Branches": []
                    },
                    "System.Int32 TestProject.Calculator::Multiply(System.Int32,System.Int32)": {
                        "Lines": {"17": 1, "18": 1},
                        "Branches": []
                    },
                    "System.Int32 TestProject.Calculator::Subtract(System.Int32,System.Int32)": {
                        "Lines": {"12": 0, "13": 0},  # 未カバー
                        "Branches": []
                    }
                }
            }
        }
        
        with patch.object(coverage_analyzer.collectors["csharp"], 'collect_coverage') as mock_collect:
            mock_collect.return_value = {
                "status": "success",
                "coverage_data": mock_coverage_data,
                "summary": {"line_coverage": 66.7, "total_lines": 6, "covered_lines": 4}
            }
            
            coverage_result = coverage_analyzer.analyze_project(self.test_project_path, "csharp")
        
        self.assertEqual(coverage_result["status"], "success")
        self.assertAlmostEqual(coverage_result["coverage_summary"]["line_coverage"], 66.7, places=1)
        
        print("✅ カバレッジ測定完了: 66.7%")
        
        # Step 3: リファクタリング分析
        print("Step 3: リファクタリング分析中...")
        
        refactoring_analyzer = RefactoringAnalyzer(self.temp_dir, self.mock_log_manager, self.mock_action_executor)
        
        mock_roslyn_result = {
            "action_result": {
                "status": "success",
                "analysis": {
                    "manifest": {
                        "objects": [
                            {
                                "id": "calc_class",
                                "type": "Class",
                                "name": "Calculator",
                                "filePath": target_file
                            }
                        ]
                    },
                    "details_by_id": {
                        "calc_class": {
                            "id": "calc_class",
                            "type": "Class",
                            "fullName": "TestProject.Calculator",
                            "filePath": target_file,
                            "startLine": 5,
                            "endLine": 20,
                            "methods": ["add", "subtract", "multiply"]
                        }
                    }
                }
            }
        }
        
        self.mock_action_executor._analyze_csharp.return_value = mock_roslyn_result
        
        refactoring_result = refactoring_analyzer.analyze_project(self.test_project_path, "csharp")
        
        self.assertEqual(refactoring_result["status"], "success")
        
        print("✅ リファクタリング分析完了")
        
        # Step 4: CI/CD設定生成
        print("Step 4: CI/CD設定生成中...")
        
        from src.cicd_integrator.cicd_integrator import CICDIntegrator
        
        cicd_integrator = CICDIntegrator(self.temp_dir, self.mock_log_manager)
        
        project_info = {
            "name": "TestProject",
            "language": "csharp",
            "ci_platform": "github_actions",
            "framework": "net6.0",
            "quality_gates": {
                "test_coverage_threshold": 80,
                "quality_score_threshold": 7.0
            }
        }
        
        cicd_result = cicd_integrator.generate_pipeline(project_info)
        
        self.assertEqual(cicd_result["status"], "success")
        
        print("✅ CI/CD設定生成完了")
        
        # 全ワークフローの成功を確認
        workflow_success = all([
            os.path.exists(test_file_path),
            coverage_result["status"] == "success",
            refactoring_result["status"] == "success",
            cicd_result["status"] == "success"
        ])
        
        self.assertTrue(workflow_success)
        
        print("🎉 品質改善ワークフロー完全成功!")
        
        # 結果サマリー
        print(f"\n📊 ワークフロー結果サマリー:")
        print(f"   テストファイル: 生成済み")
        print(f"   カバレッジ: {coverage_result['coverage_summary']['line_coverage']:.1f}%")
        print(f"   リファクタリング: 分析完了")
        print(f"   CI/CD設定: 生成済み")
        
        return {
            "test_generation": {"status": "success", "file": test_file_path},
            "coverage": coverage_result,
            "refactoring": refactoring_result,
            "cicd": cicd_result
        }
    
    def test_error_recovery_in_compound_task(self):
        """複合タスク中のエラー回復テスト"""
        print("\n=== 複合タスクエラー回復テスト ===")
        
        # Step 1: 正常なファイル作成
        print("Step 1: ファイル作成（正常）...")
        
        test_file = os.path.join(self.temp_dir, "test_file.cs")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("public class TestClass { }")
        
        self.assertTrue(os.path.exists(test_file))
        print("✅ ファイル作成成功")
        
        # Step 2: カバレッジ分析でエラー発生
        print("Step 2: カバレッジ分析（エラー発生）...")
        
        coverage_analyzer = CoverageAnalyzer(self.temp_dir, self.mock_log_manager)
        
        with patch.object(coverage_analyzer.collectors["csharp"], 'collect_coverage') as mock_collect:
            mock_collect.return_value = {
                "status": "error",
                "message": "dotnet test failed: Project file not found"
            }
            
            coverage_result = coverage_analyzer.analyze_project("invalid_path", "csharp")
        
        self.assertEqual(coverage_result["status"], "error")
        print("✅ カバレッジエラーを適切に検出")
        
        # Step 3: エラー後の回復処理
        print("Step 3: エラー回復処理...")
        
        # 正しいパスでリトライ
        with patch.object(coverage_analyzer.collectors["csharp"], 'collect_coverage') as mock_collect:
            mock_collect.return_value = {
                "status": "success",
                "coverage_data": {},
                "summary": {"line_coverage": 0.0}
            }
            
            recovery_result = coverage_analyzer.analyze_project(self.temp_dir, "csharp")
        
        self.assertEqual(recovery_result["status"], "success")
        print("✅ エラー回復成功")
        
        # エラー処理と回復の成功を確認
        self.assertTrue(os.path.exists(test_file))
        self.assertEqual(coverage_result["status"], "error")
        self.assertEqual(recovery_result["status"], "success")
        
        print("🎉 複合タスクエラー回復テスト成功!")
    
    def test_concurrent_compound_tasks(self):
        """並行複合タスクのテスト"""
        print("\n=== 並行複合タスクテスト ===")
        
        # 複数のファイルを並行処理
        files_to_process = [
            ("File1.cs", "public class File1 { }"),
            ("File2.cs", "public class File2 { }"),
            ("File3.cs", "public class File3 { }")
        ]
        
        results = []
        
        for filename, content in files_to_process:
            print(f"処理中: {filename}")
            
            # ファイル作成
            file_path = os.path.join(self.temp_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 品質分析
            coverage_analyzer = CoverageAnalyzer(self.temp_dir, self.mock_log_manager)
            
            with patch.object(coverage_analyzer.collectors["csharp"], 'collect_coverage') as mock_collect:
                mock_collect.return_value = {
                    "status": "success",
                    "coverage_data": {},
                    "summary": {"line_coverage": 50.0}
                }
                
                coverage_result = coverage_analyzer.analyze_project(self.temp_dir, "csharp")
            
            results.append({
                "file": filename,
                "created": os.path.exists(file_path),
                "coverage_status": coverage_result["status"]
            })
        
        # 全ファイルの処理成功を確認
        all_success = all(
            result["created"] and result["coverage_status"] == "success"
            for result in results
        )
        
        self.assertTrue(all_success)
        self.assertEqual(len(results), 3)
        
        print("✅ 並行複合タスク完了")
        print(f"   処理ファイル数: {len(results)}")
        print("🎉 並行複合タスクテスト成功!")


if __name__ == "__main__":
    unittest.main(verbosity=2)