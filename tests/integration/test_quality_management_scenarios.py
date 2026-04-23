# -*- coding: utf-8 -*-
# tests/test_quality_management_scenarios.py

"""
品質管理機能の実用性シナリオテスト
実際の開発ワークフローでの品質分析統合機能をテスト
"""

import unittest
import os
import tempfile
import shutil
import json
import time
from unittest.mock import Mock, patch, MagicMock
from src.coverage_analyzer.coverage_analyzer import CoverageAnalyzer
from src.refactoring_analyzer.refactoring_analyzer import RefactoringAnalyzer
from src.cicd_integrator.cicd_integrator import CICDIntegrator


class TestQualityManagementScenarios(unittest.TestCase):
    """品質管理機能の実用性シナリオテストクラス"""
    
    def setUp(self):
        """テスト前の準備"""
        self.temp_dir = tempfile.mkdtemp()
        self.mock_log_manager = Mock()
        self.mock_action_executor = Mock()
        
        # テスト用C#プロジェクト構造を作成
        self.test_project_path = os.path.join(self.temp_dir, "TestProject")
        self._create_test_csharp_project()
        
        # 各アナライザーを初期化
        self.coverage_analyzer = CoverageAnalyzer(self.temp_dir, self.mock_log_manager)
        self.refactoring_analyzer = RefactoringAnalyzer(self.temp_dir, self.mock_log_manager, self.mock_action_executor)
        self.cicd_integrator = CICDIntegrator(self.temp_dir, self.mock_log_manager)
    
    def tearDown(self):
        """テスト後のクリーンアップ"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def _create_test_csharp_project(self):
        """テスト用C#プロジェクトを作成"""
        os.makedirs(self.test_project_path, exist_ok=True)
        
        # Calculator.cs - リファクタリング対象のコード
        calculator_code = '''using System;

namespace TestProject
{
    public class Calculator
    {
        // 長いメソッド（リファクタリング対象）
        public decimal ComplexCalculation(decimal a, decimal b, decimal c, decimal d, decimal e)
        {
            if (a < 0) throw new ArgumentException("a cannot be negative");
            if (b < 0) throw new ArgumentException("b cannot be negative");
            if (c < 0) throw new ArgumentException("c cannot be negative");
            if (d < 0) throw new ArgumentException("d cannot be negative");
            if (e < 0) throw new ArgumentException("e cannot be negative");
            
            decimal result = 0;
            
            // 複雑な計算ロジック
            if (a > 0 && b > 0 && c > 0 && d > 0 && e > 0)
            {
                result = (a * b) + (c * d) + e;
                result = result * 1.1m; // 10%のボーナス
                
                if (result > 1000)
                {
                    result = result * 0.9m; // 大きな値には割引
                }
                else if (result > 500)
                {
                    result = result * 0.95m; // 中程度の値には小さな割引
                }
            }
            else
            {
                result = a + b + c + d + e;
            }
            
            return Math.Round(result, 2);
        }
        
        // 重複コード（リファクタリング対象）
        public decimal Add(decimal x, decimal y)
        {
            if (x < 0) throw new ArgumentException("x cannot be negative");
            if (y < 0) throw new ArgumentException("y cannot be negative");
            return x + y;
        }
        
        // 重複コード（リファクタリング対象）
        public decimal Subtract(decimal x, decimal y)
        {
            if (x < 0) throw new ArgumentException("x cannot be negative");
            if (y < 0) throw new ArgumentException("y cannot be negative");
            return x - y;
        }
        
        // 未テストメソッド（カバレッジ対象）
        public decimal Divide(decimal x, decimal y)
        {
            if (y == 0) throw new DivideByZeroException();
            return x / y;
        }
    }
}'''
        
        with open(os.path.join(self.test_project_path, "Calculator.cs"), 'w', encoding='utf-8') as f:
            f.write(calculator_code)
        
        # TestProject.csproj
        csproj_content = '''<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net6.0</TargetFramework>
    <Nullable>enable</Nullable>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="coverlet.collector" Version="3.1.2" />
  </ItemGroup>
</Project>'''
        
        with open(os.path.join(self.test_project_path, "TestProject.csproj"), 'w', encoding='utf-8') as f:
            f.write(csproj_content)
        
        # 部分的なテストファイル（カバレッジ不足をシミュレート）
        test_dir = os.path.join(self.test_project_path, "Tests")
        os.makedirs(test_dir, exist_ok=True)
        
        test_code = '''using Xunit;
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
        public void ComplexCalculation_ShouldReturnResult_WhenAllPositive()
        {
            var calculator = new Calculator();
            var result = calculator.ComplexCalculation(1, 2, 3, 4, 5);
            Assert.True(result > 0);
        }
        
        // Divideメソッドのテストは意図的に不足
    }
}'''
        
        with open(os.path.join(test_dir, "CalculatorTests.cs"), 'w', encoding='utf-8') as f:
            f.write(test_code)
    
    def test_complete_quality_analysis_workflow(self):
        """完全な品質分析ワークフローのテスト"""
        print("\n=== 完全品質分析ワークフロー実行 ===")
        
        # Step 1: カバレッジ分析
        print("Step 1: カバレッジ分析実行中...")
        
        # カバレッジ分析のモック（実際のdotnet testは実行しない）
        mock_coverage_data = {
            os.path.join(self.test_project_path, "Calculator.cs"): {
                "TestProject.Calculator": {
                    "System.Decimal TestProject.Calculator::Add(System.Decimal,System.Decimal)": {
                        "Lines": {"10": 1, "11": 1, "12": 1},
                        "Branches": []
                    },
                    "System.Decimal TestProject.Calculator::ComplexCalculation(System.Decimal,System.Decimal,System.Decimal,System.Decimal,System.Decimal)": {
                        "Lines": {"15": 1, "16": 1, "17": 0, "18": 0, "25": 1, "30": 0},
                        "Branches": []
                    },
                    "System.Decimal TestProject.Calculator::Divide(System.Decimal,System.Decimal)": {
                        "Lines": {"45": 0, "46": 0},
                        "Branches": []
                    }
                }
            }
        }
        
        with patch.object(self.coverage_analyzer.collectors["csharp"], 'collect_coverage') as mock_collect:
            mock_collect.return_value = {
                "status": "success",
                "coverage_data": mock_coverage_data,
                "summary": {
                    "line_coverage": 62.5,  # 5/8 lines covered
                    "method_coverage": 66.7,  # 2/3 methods covered
                    "total_lines": 8,
                    "covered_lines": 5
                }
            }
            
            coverage_result = self.coverage_analyzer.analyze_project(self.test_project_path, "csharp")
        
        # カバレッジ結果の検証
        self.assertEqual(coverage_result["status"], "success")
        self.assertAlmostEqual(coverage_result["coverage_summary"]["line_coverage"], 62.5, places=1)
        self.assertGreater(len(coverage_result["gap_analysis"]["uncovered_files"]), 0)
        
        print(f"✅ カバレッジ分析完了: {coverage_result['coverage_summary']['line_coverage']:.1f}%")
        print(f"   未カバーファイル: {len(coverage_result['gap_analysis']['uncovered_files'])}個")
        
        # Step 2: リファクタリング分析
        print("Step 2: リファクタリング分析実行中...")
        
        # MyRoslynAnalyzerのモック
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
                                "filePath": os.path.join(self.test_project_path, "Calculator.cs")
                            },
                            {
                                "id": "complex_method",
                                "type": "Method", 
                                "name": "ComplexCalculation",
                                "filePath": os.path.join(self.test_project_path, "Calculator.cs")
                            }
                        ]
                    },
                    "details_by_id": {
                        "calc_class": {
                            "id": "calc_class",
                            "type": "Class",
                            "fullName": "TestProject.Calculator",
                            "filePath": os.path.join(self.test_project_path, "Calculator.cs"),
                            "startLine": 5,
                            "endLine": 50,
                            "metrics": {
                                "lineCount": 45
                            },
                            "methods": ["complex_method", "add_method", "subtract_method", "divide_method"]
                        },
                        "complex_method": {
                            "id": "complex_method",
                            "type": "Method",
                            "name": "ComplexCalculation",
                            "fullName": "TestProject.Calculator.ComplexCalculation",
                            "filePath": os.path.join(self.test_project_path, "Calculator.cs"),
                            "startLine": 8,
                            "endLine": 35,  # 27行の長いメソッド
                            "metrics": {
                                "cyclomaticComplexity": 8,
                                "lineCount": 27,
                                "bodyHash": "complex_hash_123"
                            }
                        }
                    }
                }
            }
        }
        
        self.mock_action_executor._analyze_csharp.return_value = mock_roslyn_result
        
        refactoring_result = self.refactoring_analyzer.analyze_project(self.test_project_path, "csharp")
        
        # リファクタリング結果の検証
        self.assertEqual(refactoring_result["status"], "success")
        self.assertGreater(len(refactoring_result["code_smells"]), 0)
        self.assertGreater(len(refactoring_result["refactoring_suggestions"]), 0)
        
        print(f"✅ リファクタリング分析完了: {len(refactoring_result['code_smells'])}個のスメル検出")
        print(f"   改善提案: {len(refactoring_result['refactoring_suggestions'])}個")
        
        # Step 3: CI/CD統合設定生成
        print("Step 3: CI/CD統合設定生成中...")
        
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
        
        cicd_result = self.cicd_integrator.generate_pipeline(project_info)
        
        # CI/CD結果の検証
        self.assertEqual(cicd_result["status"], "success")
        self.assertEqual(cicd_result["platform"], "github_actions")
        self.assertIn("pipeline_config", cicd_result)
        self.assertGreater(len(cicd_result["quality_gates"]), 0)
        
        print(f"✅ CI/CD設定生成完了: {len(cicd_result['quality_gates'])}個の品質ゲート")
        
        # Step 4: 統合レポート生成
        print("Step 4: 統合レポート生成中...")
        
        reports = [
            {
                "type": "coverage",
                "line_coverage": coverage_result["coverage_summary"]["line_coverage"],
                "branch_coverage": coverage_result["coverage_summary"].get("branch_coverage", 0),
                "total_tests": 2,
                "passed_tests": 2
            },
            {
                "type": "refactoring",
                "quality_metrics": refactoring_result["quality_metrics"],
                "code_smells": refactoring_result["code_smells"]
            }
        ]
        
        integration_result = self.cicd_integrator.integrate_quality_reports(reports)
        
        # 統合結果の検証
        self.assertEqual(integration_result["status"], "success")
        self.assertIn("integrated_report", integration_result)
        self.assertGreater(len(integration_result["integrated_report"]["recommended_actions"]), 0)
        
        print(f"✅ 統合レポート生成完了")
        print(f"   総合スコア: {integration_result['integrated_report']['overall_score']:.1f}")
        print(f"   推奨アクション: {len(integration_result['integrated_report']['recommended_actions'])}個")
        
        # 全体的な品質管理ワークフローの成功を確認
        self.assertTrue(all([
            coverage_result["status"] == "success",
            refactoring_result["status"] == "success", 
            cicd_result["status"] == "success",
            integration_result["status"] == "success"
        ]))
        
        print("\n🎉 完全品質分析ワークフロー成功!")
        return {
            "coverage": coverage_result,
            "refactoring": refactoring_result,
            "cicd": cicd_result,
            "integration": integration_result
        }
    
    def test_coverage_to_refactoring_integration(self):
        """カバレッジ→リファクタリング統合テスト"""
        print("\n=== カバレッジ→リファクタリング統合テスト ===")
        
        # カバレッジ分析結果をリファクタリング分析に渡す
        coverage_data = {
            "line_coverage": 65.0,
            "uncovered_files": ["Calculator.cs"],
            "uncovered_methods": ["Divide"]
        }
        
        # リファクタリング分析でカバレッジデータを考慮
        mock_roslyn_result = {
            "action_result": {
                "status": "success",
                "analysis": {
                    "manifest": {"objects": []},
                    "details_by_id": {}
                }
            }
        }
        
        self.mock_action_executor._analyze_csharp.return_value = mock_roslyn_result
        
        refactoring_options = {
            "coverage_data": coverage_data,
            "prioritize_uncovered": True
        }
        
        result = self.refactoring_analyzer.analyze_project(
            self.test_project_path, 
            "csharp", 
            refactoring_options
        )
        
        self.assertEqual(result["status"], "success")
        print("✅ カバレッジデータがリファクタリング分析に正しく統合されました")
    
    def test_quality_gate_evaluation(self):
        """品質ゲート評価テスト"""
        print("\n=== 品質ゲート評価テスト ===")
        
        # 品質メトリクス
        metrics = {
            "coverage": 75.0,
            "quality_score": 6.5,
            "high_priority_smells": 2,
            "medium_priority_smells": 4,
            "all_tests_pass": True
        }
        
        # 品質ゲート設定
        quality_config = {
            "test_coverage_threshold": 80,
            "quality_score_threshold": 7.0,
            "max_high_priority_smells": 1
        }
        
        gates_result = self.cicd_integrator.setup_quality_gates(quality_config, "csharp")
        self.assertEqual(gates_result["status"], "success")
        
        # 各ゲートの評価
        gates = gates_result["gates"]
        gate_results = []
        
        for gate in gates:
            gate_result = self.cicd_integrator.quality_gate_manager.evaluate_gate(gate, metrics)
            gate_results.append(gate_result)
            
            print(f"   ゲート '{gate['name']}': {'✅ 通過' if gate_result['result'] else '❌ 失敗'}")
        
        # 失敗したゲートがあることを確認（カバレッジ不足、品質スコア不足）
        failed_gates = [g for g in gate_results if not g["result"]]
        self.assertGreater(len(failed_gates), 0)
        
        print(f"✅ 品質ゲート評価完了: {len(failed_gates)}個のゲートが失敗")
    
    def test_error_handling_in_workflow(self):
        """ワークフロー中のエラーハンドリングテスト"""
        print("\n=== エラーハンドリングテスト ===")
        
        # カバレッジ測定失敗のシミュレーション
        with patch.object(self.coverage_analyzer.collectors["csharp"], 'collect_coverage') as mock_collect:
            mock_collect.return_value = {
                "status": "error",
                "message": "dotnet test failed: Project not found"
            }
            
            coverage_result = self.coverage_analyzer.analyze_project("invalid_path", "csharp")
            
            self.assertEqual(coverage_result["status"], "error")
            self.assertIn("message", coverage_result)
            
        print("✅ カバレッジ測定エラーが適切に処理されました")
        
        # リファクタリング分析でのActionExecutor未設定エラー
        analyzer_without_executor = RefactoringAnalyzer(self.temp_dir, self.mock_log_manager, None)
        refactoring_result = analyzer_without_executor.analyze_project(self.test_project_path, "csharp")
        
        self.assertEqual(refactoring_result["status"], "error")
        self.assertIn("ActionExecutorが設定されていません", refactoring_result["message"])
        
        print("✅ リファクタリング分析エラーが適切に処理されました")
    
    def test_large_project_simulation(self):
        """大規模プロジェクトシミュレーションテスト"""
        print("\n=== 大規模プロジェクトシミュレーション ===")
        
        # 大規模プロジェクトのモックデータ
        large_coverage_data = {}
        for i in range(50):  # 50ファイルをシミュレート
            file_path = os.path.join(self.test_project_path, f"Class{i}.cs")
            large_coverage_data[file_path] = {
                f"TestProject.Class{i}": {
                    f"System.Void TestProject.Class{i}::Method{j}()": {
                        "Lines": {str(k): 1 if k % 3 != 0 else 0 for k in range(10, 20)},
                        "Branches": []
                    } for j in range(5)  # 各クラス5メソッド
                }
            }
        
        with patch.object(self.coverage_analyzer.collectors["csharp"], 'collect_coverage') as mock_collect:
            mock_collect.return_value = {
                "status": "success",
                "coverage_data": large_coverage_data,
                "summary": {
                    "line_coverage": 67.0,
                    "total_lines": 2500,
                    "covered_lines": 1675
                }
            }
            
            # 大規模プロジェクトでのカバレッジ分析
            start_time = time.time()
            coverage_result = self.coverage_analyzer.analyze_project(self.test_project_path, "csharp")
            analysis_time = time.time() - start_time
            
            self.assertEqual(coverage_result["status"], "success")
            self.assertLess(analysis_time, 10.0)  # 10秒以内で完了
            
        print(f"✅ 大規模プロジェクト分析完了: {analysis_time:.2f}秒")
        print(f"   分析ファイル数: 50個, 総行数: 2500行")


if __name__ == "__main__":
    unittest.main(verbosity=2)