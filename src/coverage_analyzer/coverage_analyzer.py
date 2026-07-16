# -*- coding: utf-8 -*-
# src/coverage_analyzer/coverage_analyzer.py

"""
カバレッジ分析統合モジュール
テストカバレッジの測定、分析、レポート生成を提供
"""

import os
import json
import sys
import subprocess
import ast  # For Python complexity calculation
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


class CoverageAnalyzer:
    """カバレッジ分析の中心的なコントローラー"""

    def __init__(self, workspace_root: str = ".", log_manager=None):
        self.workspace_root = Path(workspace_root)
        self.log_manager = log_manager
        self.config = self._load_coverage_config()
        self.collectors = {
            "csharp": CSharpCoverageCollector(self.config.get("csharp", {})),
            "python": PythonCoverageCollector(self.config.get("python", {})),
            "javascript": JavaScriptCoverageCollector(self.config.get("javascript", {}))
        }

    def _load_coverage_config(self) -> Dict[str, Any]:
        """カバレッジ設定を読み込む"""
        config_path = self.workspace_root / "config" / "coverage_config.json"

        default_config = {
            "csharp": {
                "tool": "coverlet",
                "command_template": "dotnet test /p:CollectCoverage=true /p:CoverletOutputFormat=json /p:CoverletOutput={output_path}",
                "exclude_patterns": ["**/bin/**", "**/obj/**", "**/*.Tests/**"],
                "thresholds": {"line": 80, "branch": 70, "method": 90}
            },
            "python": {
                "tool": "coverage",
                "command_template": "coverage run -m pytest {test_path} && coverage json -o {output_path}",
                "exclude_patterns": ["**/venv/**", "**/__pycache__/**", "**/test_*.py"],
                "thresholds": {"line": 85, "branch": 75}
            },
            "javascript": {
                "tool": "jest",
                "command_template": "jest --coverage --coverageReporters=json --coverageDirectory={output_path}",
                "exclude_patterns": ["**/node_modules/**", "**/dist/**", "**/*.test.js"],
                "thresholds": {"line": 80, "branch": 70, "function": 85}
            }
        }

        try:
            if config_path.exists():
                with config_path.open('r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                for lang in default_config:
                    if lang in loaded_config:
                        default_config[lang].update(loaded_config[lang])
                return default_config
        except Exception as e:
            if self.log_manager:
                self.log_manager.log_event("coverage_config_error", {"error": str(e)}, "WARNING")

        return default_config

    def analyze_project(self, project_path: str, language: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """プロジェクトのカバレッジ分析を実行"""
        options = options or {}
        roslyn_data = options.get("roslyn_data")

        try:
            if self.log_manager:
                self.log_manager.log_event("coverage_analysis_start", {
                    "project_path": project_path,
                    "language": language,
                    "has_roslyn_data": roslyn_data is not None
                })

            coverage_result = self._measure_coverage(project_path, language, options)
            if coverage_result["status"] != "success":
                return coverage_result

            # ギャップ分析に roslyn_data を渡す
            gap_analysis = self._analyze_gaps(coverage_result["coverage_data"], project_path, language, roslyn_data)

            quality_metrics = self._analyze_quality(coverage_result["coverage_data"], gap_analysis)
            recommendations = self._generate_recommendations(gap_analysis, quality_metrics, language)
            reports = self._generate_reports(coverage_result, gap_analysis, quality_metrics, recommendations, options)

            result = {
                "status": "success",
                "project_path": project_path,
                "language": language,
                "coverage_summary": coverage_result["summary"],
                "gap_analysis": gap_analysis,
                "recommendations": recommendations,
                "reports": reports,
                "quality_metrics": quality_metrics,
                "timestamp": datetime.now().isoformat()
            }

            return result
        except Exception as e:
            return {"status": "error", "message": f"カバレッジ分析中にエラーが発生しました: {str(e)}"}

    def _measure_coverage(self, project_path: str, language: str, options: Dict[str, Any]) -> Dict[str, Any]:
        if language not in self.collectors:
            return {"status": "error", "message": f"サポートされていない言語です: {language}"}
        return self.collectors[language].collect_coverage(project_path, options)

    def _analyze_gaps(self, coverage_data: Dict[str, Any], project_path: str, language: str, roslyn_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        gap_analyzer = GapAnalyzer(language)
        return gap_analyzer.analyze(coverage_data, project_path, roslyn_data)

    def _analyze_quality(self, coverage_data: Dict[str, Any], gap_analysis: Dict[str, Any]) -> Dict[str, Any]:
        quality_analyzer = QualityAnalyzer()
        return quality_analyzer.analyze(coverage_data, gap_analysis)

    def _generate_recommendations(self, gap_analysis: Dict[str, Any], quality_metrics: Dict[str, Any], language: str) -> List[Dict[str, Any]]:
        recommendation_engine = RecommendationEngine(language)
        return recommendation_engine.generate(gap_analysis, quality_metrics)

    def _generate_reports(self, coverage_result: Dict[str, Any], gap_analysis: Dict[str, Any],
                         quality_metrics: Dict[str, Any], recommendations: List[Dict[str, Any]],
                         options: Dict[str, Any]) -> Dict[str, str]:
        output_formats = options.get("output_formats", ["json", "text"])
        reports = {}
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_dir = os.path.join(self.workspace_root, "coverage_reports")
        os.makedirs(report_dir, exist_ok=True)

        if "json" in output_formats:
            json_path = os.path.join(report_dir, f"coverage_{timestamp}.json")
            JSONReporter().generate(json_path, coverage_result, gap_analysis, quality_metrics, recommendations)
            reports["json_report"] = json_path

        if "html" in output_formats:
            html_path = os.path.join(report_dir, f"coverage_{timestamp}.html")
            HTMLReporter().generate(html_path, coverage_result, gap_analysis, quality_metrics, recommendations)
            reports["html_report"] = html_path

        return reports


class GapAnalyzer:
    """カバレッジギャップ分析クラス"""

    def __init__(self, language: str):
        self.language = language

    def analyze(self, coverage_data: Dict[str, Any], project_path: str, roslyn_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """カバレッジギャップを分析"""
        uncovered_files = self._find_uncovered_files(coverage_data, project_path, roslyn_data)
        missing_scenarios = self._identify_missing_scenarios(coverage_data, project_path)

        return {
            "uncovered_files": uncovered_files,
            "missing_test_scenarios": missing_scenarios,
            "analysis_summary": {
                "total_uncovered_files": len(uncovered_files),
                "high_priority_gaps": len([f for f in uncovered_files if f.get("priority") == "high"]),
                "missing_scenarios_count": len(missing_scenarios)
            }
        }

    def _calculate_complexity(
        self,
        file_path_abs: str,
        roslyn_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        ファイル内容を読み込み、複雑度を計算する。
        C#: Roslynアナライザーの結果を使用 (正確)
        Python: ASTを使用 (正確)
        JavaScript: 構造解析データが未対応のため不明
        """
        if self.language == "csharp" and roslyn_data:
            return self._get_complexity_from_roslyn(file_path_abs, roslyn_data)

        if not os.path.exists(file_path_abs):
            return None

        try:
            with open(file_path_abs, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            if self.language == "python":
                try:
                    tree = ast.parse(content)
                    complexity = 1
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor, ast.With, ast.AsyncWith, ast.Try, ast.ExceptHandler)):
                            complexity += 1
                        elif isinstance(node, ast.BoolOp):
                            complexity += len(node.values) - 1
                    return complexity
                except SyntaxError:
                    return None
            return None
        except (OSError, UnicodeError):
            return None

    def _get_complexity_from_roslyn(
        self,
        file_path_abs: str,
        roslyn_data: Dict[str, Any],
    ) -> Optional[int]:
        """Roslynの解析結果から該当ファイルの合計複雑度を取得"""
        total_complexity = 0
        metric_found = False
        manifest = roslyn_data.get("manifest", {})
        manifest_objects = (
            manifest.get("objects", [])
            if isinstance(manifest, dict)
            else manifest
        )
        details_by_id = roslyn_data.get("details_by_id", {})
        normalized_target = os.path.normcase(os.path.abspath(file_path_abs))

        for entry in manifest_objects:
            entry_path = entry.get("filePath")
            if not entry_path:
                continue
            normalized_entry = os.path.normcase(os.path.abspath(entry_path))
            if normalized_entry != normalized_target:
                continue
            detail = details_by_id.get(entry.get("id"), {})
            for method in detail.get("methods", []):
                complexity = method.get("metrics", {}).get(
                    "cyclomaticComplexity"
                )
                if isinstance(complexity, int):
                    total_complexity += complexity
                    metric_found = True

        return total_complexity if metric_found else None

    @staticmethod
    def _priority_for_gap(
        uncovered_count: int,
        complexity: Optional[int],
    ) -> str:
        if uncovered_count > 20 or (
            complexity is not None and complexity > 20
        ):
            return "high"
        if uncovered_count > 5 or (
            complexity is not None and complexity > 10
        ):
            return "medium"
        return "low"

    def _find_uncovered_files(self, coverage_data: Dict[str, Any], project_path: str, roslyn_data: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        uncovered_files_list = []

        if self.language == "csharp":
            for file_path_abs, file_data in coverage_data.items():
                uncovered_lines_in_file = []
                uncovered_methods_in_file = set()
                file_has_uncovered_lines = False

                for class_name, class_data in file_data.items():
                    for method_signature, method_data in class_data.items():
                        method_name = method_signature.split('::')[-1].split('(')[0]
                        lines_data = method_data.get("Lines", {})
                        method_has_code = False
                        method_fully_covered = True

                        for line_number, hit_count in lines_data.items():
                            method_has_code = True
                            if hit_count == 0:
                                uncovered_lines_in_file.append(int(line_number))
                                file_has_uncovered_lines = True
                                method_fully_covered = False

                        if method_has_code and not method_fully_covered:
                            uncovered_methods_in_file.add(method_name)

                if file_has_uncovered_lines:
                    rel_file_path = os.path.relpath(file_path_abs, project_path)
                    calculated_complexity_score = self._calculate_complexity(file_path_abs, roslyn_data)
                    uncovered_lines_count = len(uncovered_lines_in_file)
                    calculated_priority = self._priority_for_gap(
                        uncovered_lines_count,
                        calculated_complexity_score,
                    )

                    uncovered_files_list.append({
                        "file": rel_file_path,
                        "uncovered_lines": sorted(list(set(uncovered_lines_in_file))),
                        "uncovered_methods": sorted(list(uncovered_methods_in_file)),
                        "complexity_score": calculated_complexity_score,
                        "priority": calculated_priority
                    })
        elif self.language == "python":
            files_data = coverage_data.get("files", {})
            for file_path_abs, file_info in files_data.items():
                if file_info.get("missing_lines"):
                    rel_file_path = os.path.relpath(file_path_abs, project_path)
                    calculated_complexity_score = self._calculate_complexity(file_path_abs)
                    missing_lines_count = len(file_info["missing_lines"])
                    calculated_priority = self._priority_for_gap(
                        missing_lines_count,
                        calculated_complexity_score,
                    )
                    uncovered_files_list.append({
                        "file": rel_file_path,
                        "uncovered_lines": file_info["missing_lines"],
                        "uncovered_methods": [],
                        "complexity_score": calculated_complexity_score,
                        "priority": calculated_priority
                    })
        elif self.language == "javascript":
            for file_path_abs, file_data in coverage_data.items():
                if isinstance(file_data, dict):
                    statements = file_data.get("s", {})
                    uncovered_lines_in_file = [int(l) for l, h in statements.items() if h == 0]
                    if uncovered_lines_in_file:
                        rel_file_path = os.path.relpath(file_path_abs, project_path)
                        calculated_complexity_score = self._calculate_complexity(file_path_abs)
                        calculated_priority = self._priority_for_gap(
                            len(uncovered_lines_in_file),
                            calculated_complexity_score,
                        )
                        uncovered_files_list.append({
                            "file": rel_file_path,
                            "uncovered_lines": sorted(uncovered_lines_in_file),
                            "uncovered_methods": [],
                            "complexity_score": calculated_complexity_score,
                            "priority": calculated_priority
                        })

        return uncovered_files_list

    def _identify_missing_scenarios(self, coverage_data: Dict[str, Any], project_path: str) -> List[Dict[str, Any]]:
        missing_scenarios = []
        if self.language == "csharp":
            for file_path_abs, file_data in coverage_data.items():
                for class_name, class_data in file_data.items():
                    for method_signature, method_data in class_data.items():
                        method_name = method_signature.split('::')[-1].split('(')[0]
                        lines_data = method_data.get("Lines", {})
                        if not lines_data: continue
                        uncovered_lines = [int(line) for line, hit in lines_data.items() if hit == 0]
                        if not uncovered_lines: continue
                        if len(uncovered_lines) == len(lines_data):
                            missing_scenarios.append({
                                "target_method": method_name,
                                "scenario": f"{method_name} の基本動作確認",
                                "suggested_test": f"{method_name}_ShouldReturnResult_WhenValidInput",
                                "priority": "high"
                            })
                        else:
                            missing_scenarios.append({
                                "target_method": method_name,
                                "scenario": f"{method_name} の行 {uncovered_lines} 周辺のエッジケース",
                                "suggested_test": f"{method_name}_ShouldHandleEdgeCase",
                                "priority": "medium"
                            })
        return missing_scenarios

class QualityAnalyzer:
    """品質メトリクス分析クラス"""
    def analyze(self, coverage_data: Dict[str, Any], gap_analysis: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "coverage_trend": "unknown",
            "quality_score": self._calculate_quality_score(coverage_data, gap_analysis),
            "technical_debt": self._assess_technical_debt(gap_analysis),
            "maintainability_index": self._calculate_maintainability_index(coverage_data, gap_analysis)
        }
    def _calculate_quality_score(self, coverage_data: Dict[str, Any], gap_analysis: Dict[str, Any]) -> float:
        summary = coverage_data.get("summary", {})
        line_coverage = summary.get("line_coverage", 0.0)
        base_score = line_coverage / 10.0
        penalty = min(1.0, len(gap_analysis.get("uncovered_files", [])) * 0.1)
        penalty += min(2.0, gap_analysis.get("analysis_summary", {}).get("high_priority_gaps", 0) * 0.5)
        return round(max(0.0, base_score - penalty), 1)
    def _assess_technical_debt(self, gap_analysis: Dict[str, Any]) -> str:
        summary = gap_analysis.get("analysis_summary", {})
        if summary.get("high_priority_gaps", 0) > 5: return "high"
        if summary.get("total_uncovered_files", 0) > 5: return "medium"
        return "low"
    def _calculate_maintainability_index(self, coverage_data: Dict[str, Any], gap_analysis: Dict[str, Any]) -> int:
        summary = coverage_data.get("summary", {})
        mi = 80 - (summary.get("total_lines", 0) * 0.005) + (summary.get("line_coverage", 0.0) * 0.2)
        return max(0, min(100, int(mi)))

class BaseCoverageCollector:
    def __init__(self, config: Dict[str, Any]): self.config = config
    def collect_coverage(self, project_path: str, options: Dict[str, Any]) -> Dict[str, Any]: raise NotImplementedError

class CSharpCoverageCollector(BaseCoverageCollector):
    def collect_coverage(self, project_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        try:
            project_path = os.path.abspath(project_path)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(project_path, "coverage_output", f"coverage_{timestamp}.json")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            command = [
                "dotnet", "test", project_path,
                "/p:CollectCoverage=true",
                "/p:CoverletOutputFormat=json",
                f"/p:CoverletOutput={output_path}",
            ]
            result = subprocess.run(
                command, capture_output=True, text=True, cwd=project_path, check=False
            )

            # Restore error handling: check return code!
            if result.returncode != 0:
                return {"status": "error", "message": f"dotnet test failed: {result.stderr}"}

            if not os.path.exists(output_path): return {"status": "error", "message": "Coverage file not generated"}
            with open(output_path, 'r', encoding='utf-8') as f: coverage_data = json.load(f)
            return {"status": "success", "coverage_data": coverage_data, "summary": self._calculate_summary(coverage_data)}
        except Exception as e: return {"status": "error", "message": str(e)}

    def _calculate_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        tl, cl, tm, cm, tb, cb = 0, 0, 0, 0, 0, 0
        for f, fd in data.items():
            for c, cd in fd.items():
                for m, md in cd.items():
                    tm += 1
                    mcl = 0
                    for l, h in md.get("Lines", {}).items():
                        tl += 1
                        if h > 0: cl += 1; mcl += 1
                    if mcl > 0: cm += 1
                    for b in md.get("Branches", []):
                        tb += 1
                        if b.get("Hits", 0) > 0: cb += 1
        return {"line_coverage": (cl/tl*100) if tl > 0 else 0, "branch_coverage": (cb/tb*100) if tb > 0 else 0, "method_coverage": (cm/tm*100) if tm > 0 else 0, "total_lines": tl, "covered_lines": cl}

class PythonCoverageCollector(BaseCoverageCollector):
    def collect_coverage(self, project_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        try:
            project_path = os.path.abspath(project_path)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            out = os.path.join(project_path, f"coverage_{timestamp}.json")
            tp = options.get("test_path", "tests/unit")

            test_result = subprocess.run(
                [
                    sys.executable, "-m", "coverage", "run", "--source=src",
                    "-m", "unittest", "discover", tp,
                ],
                capture_output=True,
                text=True,
                cwd=project_path,
                check=False,
            )
            if test_result.returncode != 0:
                return {
                    "status": "error",
                    "message": f"coverage test run failed: {test_result.stderr}",
                }

            report_result = subprocess.run(
                [sys.executable, "-m", "coverage", "json", "-o", out],
                capture_output=True,
                text=True,
                cwd=project_path,
                check=False,
            )
            if report_result.returncode != 0:
                return {
                    "status": "error",
                    "message": f"coverage report failed: {report_result.stderr}",
                }

            if not os.path.exists(out):
                return {"status": "error", "message": "Coverage JSON file not generated"}

            with open(out, 'r') as f:
                data = json.load(f)
            t = data.get("totals", {})
            return {
                "status": "success",
                "coverage_data": data,
                "summary": {
                    "line_coverage": t.get("percent_covered", 0),
                    "total_lines": t.get("num_statements", 0),
                    "covered_lines": t.get("covered_lines", 0)
                }
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

class JavaScriptCoverageCollector(BaseCoverageCollector):
    def collect_coverage(self, project_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        try:
            project_path = os.path.abspath(project_path)
            out = os.path.join(project_path, f"coverage_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            result = subprocess.run(
                [
                    "jest", "--coverage", "--coverageReporters=json",
                    f"--coverageDirectory={out}",
                ],
                capture_output=True,
                text=True,
                cwd=project_path,
                check=False,
            )
            if result.returncode != 0:
                return {"status": "error", "message": f"jest failed: {result.stderr}"}
            with open(os.path.join(out, "coverage-final.json"), 'r') as f: data = json.load(f)
            tl, cl = 0, 0
            for f, fd in data.items():
                s = fd.get("s", {})
                tl += len(s)
                cl += sum(1 for h in s.values() if h > 0)
            return {"status": "success", "coverage_data": data, "summary": {"line_coverage": (cl/tl*100) if tl > 0 else 0, "total_lines": tl, "covered_lines": cl}}
        except Exception as e: return {"status": "error", "message": str(e)}

class RecommendationEngine:
    """改善提案生成クラス"""

    def __init__(self, language: str):
        self.language = language

    def generate(self, gap_analysis: Dict[str, Any], quality_metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """改善提案を生成"""
        recommendations = []

        # 未カバーメソッドのテスト追加提案
        for file_info in gap_analysis.get("uncovered_files", []):
            for method in file_info.get("uncovered_methods", []):
                recommendations.append({
                    "type": "add_test",
                    "priority": file_info.get("priority", "medium"),
                    "description": f"{file_info['file']}の{method}メソッドのテストを追加してください",
                    "suggested_test_code": self._generate_test_template(method, file_info["file"]),
                    "estimated_effort": "medium"
                })

        # 不足シナリオのテスト追加提案
        for scenario in gap_analysis.get("missing_test_scenarios", []):
            recommendations.append({
                "type": "add_scenario_test",
                "priority": scenario.get("priority", "medium"),
                "description": f"{scenario['target_method']}の{scenario['scenario']}シナリオのテストを追加してください",
                "suggested_test_name": scenario["suggested_test"],
                "estimated_effort": "low"
            })

        # 品質改善提案
        if quality_metrics.get("technical_debt") == "high":
            recommendations.append({
                "type": "refactor",
                "priority": "high",
                "description": "技術的負債が高いため、コードのリファクタリングを検討してください",
                "estimated_effort": "high"
            })

        return recommendations

    def _generate_test_template(self, method_name: str, file_name: str) -> str:
        """テストテンプレートを生成"""
        if self.language == "csharp":
            return f"""[Fact]
public void {method_name}_ShouldReturnExpectedResult_WhenValidInput()
{{
    // Arrange
    var target = new {Path(file_name).stem}();

    // Act
    var result = target.{method_name}();

    // Assert
    Assert.NotNull(result);
}}"""
        elif self.language == "python":
            return f"""def test_{method_name.lower()}_should_return_expected_result_when_valid_input(self):
    # Arrange
    target = {Path(file_name).stem}()

    # Act
    result = target.{method_name}()

    # Assert
    self.assertIsNotNone(result)"""
        else:
            return f"""test('{method_name} should return expected result when valid input', () => {{
    // Arrange
    const target = new {Path(file_name).stem}();

    // Act
    const result = target.{method_name}();

    // Assert
    expect(result).toBeDefined();
}});"""

class JSONReporter:
    def generate(self, p, res, gap, met, rec):
        with open(p, 'w', encoding='utf-8') as f: json.dump({"res": res, "gap": gap, "met": met, "rec": rec}, f, ensure_ascii=False, indent=2)

class HTMLReporter:
    def generate(self, p, res, gap, met, rec):
        with open(p, 'w', encoding='utf-8') as f: f.write(f"<html><body><h1>Coverage Report</h1><p>Score: {met.get('quality_score')}</p></body></html>")

class TextReporter:
    def generate_summary(self, res, gap, rec):
        s = res.get("summary", {})
        return f"Coverage: {s.get('line_coverage', 0):.1f}%, Gaps: {len(gap.get('uncovered_files', []))}"
