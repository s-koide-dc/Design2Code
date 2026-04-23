#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# src/cicd_integrator/quality_gate_checker.py

"""
品質ゲートチェッカー
CI/CDパイプラインで実行される品質ゲートの評価を行う
"""

import os
import sys
import json
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.cicd_integrator.cicd_integrator import QualityGateManager


class QualityGateChecker:
    """品質ゲートチェッカー"""
    
    def __init__(self, workspace_root: str = "."):
        self.workspace_root = workspace_root
        self.gate_manager = QualityGateManager(self._load_config())
    
    def _load_config(self) -> Dict[str, Any]:
        """設定を読み込む"""
        config_path = os.path.join(self.workspace_root, "resources", "cicd_config.json")
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"設定読み込みエラー: {e}", file=sys.stderr)
        
        return {}
    
    def check_gates(self, metrics_file: str = None, gates_config: Dict[str, Any] = None) -> Dict[str, Any]:
        """品質ゲートをチェック"""
        try:
            # メトリクスの読み込み
            metrics = self._load_metrics(metrics_file)
            
            # ゲート設定の取得
            if gates_config is None:
                gates_config = self._load_gates_config()
            
            # ゲートの設定
            gates = self.gate_manager.setup_gates(gates_config, metrics.get("language", "csharp"))
            
            # ゲートの評価
            results = []
            overall_status = "passed"
            
            for gate in gates:
                result = self.gate_manager.evaluate_gate(gate, metrics)
                results.append(result)
                
                # ブロッキングゲートが失敗した場合
                if gate.get("type") == "blocking" and result.get("status") != "passed":
                    overall_status = "failed"
                # 警告ゲートが失敗した場合
                elif gate.get("type") == "warning" and result.get("status") != "passed" and overall_status != "failed":
                    overall_status = "warning"
            
            return {
                "overall_status": overall_status,
                "gates": results,
                "summary": self._create_summary(results),
                "metrics": metrics
            }
            
        except Exception as e:
            return {
                "overall_status": "error",
                "error": str(e),
                "gates": [],
                "summary": {"total": 0, "passed": 0, "failed": 0, "warnings": 0}
            }
    
    def _load_metrics(self, metrics_file: str = None) -> Dict[str, Any]:
        """メトリクスを読み込む"""
        if metrics_file and os.path.exists(metrics_file):
            try:
                with open(metrics_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"メトリクスファイル読み込みエラー: {e}", file=sys.stderr)
        
        # デフォルトメトリクスまたは自動収集
        return self._collect_metrics()
    
    def _collect_metrics(self) -> Dict[str, Any]:
        """メトリクスを自動収集"""
        metrics = {
            "language": "csharp",
            "all_tests_pass": False,
            "coverage": 0.0,
            "quality_score": 0.0,
            "high_priority_smells": 0,
            "medium_priority_smells": 0,
            "low_priority_smells": 0
        }
        
        try:
            # テスト結果の確認
            test_results = self._check_test_results()
            metrics.update(test_results)
            
            # カバレッジレポートの確認
            coverage_results = self._check_coverage_results()
            metrics.update(coverage_results)
            
            # 品質レポートの確認
            quality_results = self._check_quality_results()
            metrics.update(quality_results)
            
        except Exception as e:
            print(f"メトリクス収集エラー: {e}", file=sys.stderr)
        
        return metrics
    
    def _check_test_results(self) -> Dict[str, Any]:
        """テスト結果を確認"""
        # TRX (Visual Studio Test Results)
        trx_files = self._find_files("TestResults/**/*.trx") + self._find_files("**/*.trx")
        for trx in trx_files:
            try:
                tree = ET.parse(trx)
                root = tree.getroot()
                # Namespaces in TRX are tricky, often http://microsoft.com/schemas/VisualStudio/TeamTest/2010
                # Using simple iteration to check Outcome="Failed"
                ns = {'ns': 'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}
                failed = False
                results = root.find('.//ns:Results', ns)
                if results:
                    for res in results:
                        if res.get('Outcome') == 'Failed':
                            failed = True
                            break
                if not failed:
                    # Also check Counters
                    counters = root.find('.//ns:ResultSummary/ns:Counters', ns)
                    if counters and int(counters.get('Failed', 0)) > 0:
                        failed = True
                
                if failed:
                    return {"all_tests_pass": False}
                # If we parsed a file and found no failures, assume pass for this file
                # Continue checking others? Usually one file is enough for CI run
                return {"all_tests_pass": True}
            except Exception:
                continue

        # JUnit XML
        junit_files = self._find_files("**/test-results/**/*.xml") + self._find_files("**/junit.xml")
        for xml in junit_files:
            try:
                tree = ET.parse(xml)
                root = tree.getroot()
                # JUnit format: <testsuite failures="0" errors="0" ...>
                failures = int(root.get('failures', 0))
                errors = int(root.get('errors', 0))
                
                # Check testcases
                for testcase in root.findall('.//testcase'):
                    if testcase.find('failure') is not None or testcase.find('error') is not None:
                        failures += 1
                
                if failures > 0 or errors > 0:
                    return {"all_tests_pass": False}
                return {"all_tests_pass": True}
            except Exception:
                continue

        return {"all_tests_pass": False} # Default to False if no results found
    
    def _check_coverage_results(self) -> Dict[str, Any]:
        """カバレッジ結果を確認"""
        
        # 1. Cobertura (XML)
        xml_files = self._find_files("**/coverage.cobertura.xml") + self._find_files("**/coverage.xml")
        for xml in xml_files:
            try:
                tree = ET.parse(xml)
                root = tree.getroot()
                # <coverage line-rate="0.5" ...>
                line_rate = float(root.get('line-rate', 0.0))
                return {"coverage": line_rate * 100.0}
            except Exception:
                continue

        # 2. JSON (Coverlet / Custom / coverage.py)
        json_files = self._find_files("**/coverage.json")
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    
                # Check known formats
                # custom format from CoverageAnalyzer?
                if "summary" in data and "line_coverage" in data["summary"]:
                    return {"coverage": float(data["summary"]["line_coverage"])}
                
                # coverage.py json
                if "totals" in data and "percent_covered" in data["totals"]:
                    return {"coverage": float(data["totals"]["percent_covered"])}
                
            except Exception:
                continue
        
        # 3. LCOV (Simple parsing)
        lcov_files = self._find_files("**/lcov.info")
        for lcov in lcov_files:
            try:
                total_lines = 0
                covered_lines = 0
                with open(lcov, 'r') as f:
                    for line in f:
                        if line.startswith('LF:'): # Lines Found
                            total_lines += int(line.split(':')[1])
                        if line.startswith('LH:'): # Lines Hit
                            covered_lines += int(line.split(':')[1])
                if total_lines > 0:
                    return {"coverage": (covered_lines / total_lines) * 100.0}
            except Exception:
                continue

        return {"coverage": 0.0}
    
    def _check_quality_results(self) -> Dict[str, Any]:
        """品質結果を確認"""
        quality_report_dirs = [
            "refactoring_reports",
            "quality_reports",
            "analysis_reports"
        ]
        
        for report_dir in quality_report_dirs:
            report_path = os.path.join(self.workspace_root, report_dir)
            if os.path.exists(report_path):
                # 最新のレポートファイルを探す
                latest_report = self._find_latest_report(report_path)
                if latest_report:
                    return self._parse_quality_report(latest_report)
        
        return {
            "quality_score": 0.0,
            "high_priority_smells": 0,
            "medium_priority_smells": 0,
            "low_priority_smells": 0
        }
    
    def _find_files(self, pattern: str) -> List[str]:
        """ファイルパターンに一致するファイルを検索"""
        import glob
        return glob.glob(os.path.join(self.workspace_root, pattern), recursive=True)
    
    def _find_latest_report(self, report_dir: str) -> Optional[str]:
        """最新のレポートファイルを検索"""
        try:
            json_files = []
            for root, dirs, files in os.walk(report_dir):
                for file in files:
                    if file.endswith('.json'):
                        json_files.append(os.path.join(root, file))
            
            if json_files:
                # 最新のファイルを返す
                return max(json_files, key=os.path.getmtime)
        except Exception:
            pass
        
        return None
    
    def _parse_quality_report(self, report_file: str) -> Dict[str, Any]:
        """品質レポートを解析"""
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            quality_metrics = report.get("quality_metrics", {})
            code_smells = report.get("code_smells", [])
            
            high_priority = len([s for s in code_smells if s.get("severity") == "high"])
            medium_priority = len([s for s in code_smells if s.get("severity") == "medium"])
            low_priority = len([s for s in code_smells if s.get("severity") == "low"])
            
            return {
                "quality_score": quality_metrics.get("quality_score", quality_metrics.get("overall_score", 0.0)),
                "high_priority_smells": high_priority,
                "medium_priority_smells": medium_priority,
                "low_priority_smells": low_priority
            }
            
        except Exception as e:
            print(f"品質レポート解析エラー: {e}", file=sys.stderr)
            return {
                "quality_score": 0.0,
                "high_priority_smells": 0,
                "medium_priority_smells": 0,
                "low_priority_smells": 0
            }
    
    def _load_gates_config(self) -> Dict[str, Any]:
        """ゲート設定を読み込む"""
        config = self._load_config()
        return config.get("quality_gates", {})
    
    def _create_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """結果サマリーを作成"""
        total = len(results)
        passed = len([r for r in results if r.get("status") == "passed"])
        failed = len([r for r in results if r.get("status") == "failed"])
        warnings = len([r for r in results if r.get("status") == "warning"])
        errors = len([r for r in results if r.get("status") == "error"])
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "errors": errors,
            "success_rate": (passed / total * 100) if total > 0 else 0
        }
    
    def print_results(self, results: Dict[str, Any]) -> None:
        """結果を出力"""
        overall_status = results.get("overall_status", "unknown")
        summary = results.get("summary", {})
        metrics = results.get("metrics", {})
        
        print(f"品質ゲートチェック結果: {overall_status.upper()}")
        print(f"  カバレッジ: {metrics.get('coverage', 0):.1f}%")
        print(f"  テスト通過: {'Yes' if metrics.get('all_tests_pass') else 'No'}")
        print(f"  品質スコア: {metrics.get('quality_score', 0):.1f}")
        print("-" * 20)
        print(f"総ゲート数: {summary.get('total', 0)}")
        print(f"成功: {summary.get('passed', 0)}")
        print(f"失敗: {summary.get('failed', 0)}")
        print(f"警告: {summary.get('warnings', 0)}")
        print(f"エラー: {summary.get('errors', 0)}")
        print(f"成功率: {summary.get('success_rate', 0):.1f}%")
        
        print("\n詳細結果:")
        for gate in results.get("gates", []):
            status_icon = "✅" if gate.get("status") == "passed" else "❌" if gate.get("status") == "failed" else "⚠️"
            print(f"{status_icon} {gate.get('gate_name', 'unknown')}: {gate.get('message', 'no message')}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description="品質ゲートチェッカー")
    parser.add_argument("--metrics", help="メトリクスファイルのパス")
    parser.add_argument("--workspace", default=".", help="ワークスペースルート")
    parser.add_argument("--output", help="結果出力ファイル")
    parser.add_argument("--format", choices=["json", "text"], default="text", help="出力形式")
    
    args = parser.parse_args()
    
    checker = QualityGateChecker(args.workspace)
    results = checker.check_gates(args.metrics)
    
    if args.format == "json":
        output = json.dumps(results, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output)
        else:
            print(output)
    else:
        checker.print_results(results)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(f"Quality Gate Check Results\n")
                f.write(f"Overall Status: {results.get('overall_status', 'unknown')}\n")
                f.write(f"Summary: {results.get('summary', {})}\n")
    
    # 終了コード設定
    overall_status = results.get("overall_status", "error")
    if overall_status == "passed":
        sys.exit(0)
    elif overall_status == "warning":
        sys.exit(0)  # 警告は成功として扱う
    else:
        sys.exit(1)  # 失敗またはエラー


if __name__ == "__main__":
    main()
