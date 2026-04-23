# -*- coding: utf-8 -*-
# src/test_operations/test_operations.py

import os
from typing import Dict, Any

class TestAndCoverageOperations:
    """テストおよびカバレッジ関連の操作を担当する独立モジュール"""
    
    def __init__(self, action_executor):
        self.ae = action_executor

    def generate_test_cases(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """テストケースを生成する"""
        filename = self.ae._get_entity_value(parameters.get("filename"))
        language = self.ae._get_entity_value(parameters.get("language"))

        if not filename:
            context["action_result"] = {"status": "error", "message": "テスト生成対象のファイル名が指定されていません。"}
            return context

        if not language:
            if filename.endswith(".py"):
                language = "python"
            elif filename.endswith(".js"):
                language = "javascript"
            elif filename.endswith(".cs"):
                language = "csharp"
            else:
                language = "csharp"

        path = self.ae._safe_join(filename)
        
        # --- NEW: Class Name to File Path Resolution ---
        if (not path or not os.path.exists(path)) and "." in filename:
            # Try to resolve from previous analysis results (output_path in entities or action_result)
            output_path = self.ae._get_entity_value(parameters.get("output_path"))
            if output_path and os.path.exists(output_path):
                try:
                    # Use CSharpOperations helper to load manifest
                    manifest, _ = self.ae.csharp_ops.load_csharp_analysis_results(output_path)
                    # Search for the class/method in manifest objects
                    target_obj = next((obj for obj in manifest.get("objects", []) if obj.get("fullName") == filename), None)
                    if target_obj and target_obj.get("filePath"):
                        resolved_path = target_obj.get("filePath")
                        # Some paths might be absolute or relative to workspace
                        path = self.ae._safe_join(resolved_path)
                        if path and os.path.exists(path):
                            filename = os.path.basename(path) # Use basename for reporting
                    else:
                        pass
                except Exception as e:
                    pass # Fallback to original failure if resolution fails
        # -----------------------------------------------

        if not path or not os.path.exists(path):
            context["action_result"] = {"status": "error", "message": "ファイルが見つかりません。"}
            return context

        try:
            output_path = self.ae._get_entity_value(parameters.get("output_path"))
            # Use public API for test generation to align with expected behavior and tests.
            result = self.ae.test_generator.generate_test_cases(
                source_file=path,
                language=language,
                analysis_output_path=output_path,
            )
            
            if result["status"] == "success":
                test_cases = result.get("test_cases", [])
                test_count = len(test_cases)
                
                # Check if generated_files list is present (new behavior)
                gen_files = result.get("generated_files", [])
                
                message = f"プロジェクトの解析に基づき {test_count} 個のテストシナリオを特定しました。\n"
                
                if gen_files:
                    message += f"以下のファイルにテストコードを生成・保存しました:\n"
                    for f in gen_files:
                        message += f"- {os.path.basename(f)}\n"
                
                context["action_result"] = {
                    "status": "success",
                    "message": message,
                    "test_cases": test_cases,
                    "generated_files": gen_files,
                    "analysis": result.get("analysis", {})
                }
            else:
                context["action_result"] = {"status": "error", "message": result.get("message", "テストケース生成に失敗しました。")}
                
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"テストケース生成中にエラーが発生しました: {e}")
            
        return context

    def measure_coverage(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """カバレッジを測定する"""
        project_path = self.ae._get_entity_value(parameters.get("project_path"))
        language = self.ae._get_entity_value(parameters.get("language", "csharp"))
        
        if not project_path:
            context["action_result"] = {"status": "error", "message": "プロジェクトパスが指定されていません。"}
            return context
            
        abs_project_path = self.ae._safe_join(project_path)
        if not abs_project_path or not os.path.exists(abs_project_path):
            context["action_result"] = {"status": "error", "message": f"プロジェクトパス '{project_path}' が見つかりません。"}
            return context

        try:
            options = parameters.get("options", {})
            result = self.ae.coverage_analyzer.analyze_project(abs_project_path, language, options)
            
            if result["status"] == "success":
                summary = result.get("coverage_summary", {})
                line_coverage = summary.get("line_coverage", 0)
                
                message = f"プロジェクト '{project_path}' のカバレッジ測定が完了しました。\n"
                message += f"ライン カバレッジ: {line_coverage:.1f}%\n"
                
                if "branch_coverage" in summary:
                    message += f"ブランチ カバレッジ: {summary['branch_coverage']:.1f}%\n"
                if "method_coverage" in summary:
                    message += f"メソッド カバレッジ: {summary['method_coverage']:.1f}%\n"
                
                reports = result.get("reports", {})
                if reports:
                    message += "\n生成されたレポート:\n"
                    for report_type, report_path in reports.items():
                        if report_type != "text_summary":
                            message += f"- {report_type}: {report_path}\n"
                
                context["action_result"] = {
                    "status": "success",
                    "message": message,
                    "coverage_result": result
                }
            else:
                context["action_result"] = {"status": "error", "message": result.get("message", "カバレッジ測定に失敗しました。")}
                
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"カバレッジ測定中にエラーが発生しました: {e}")
            
        return context

    def analyze_coverage_gaps(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """カバレッジギャップを分析する"""
        project_path = self.ae._get_entity_value(parameters.get("project_path"))
        language = self.ae._get_entity_value(parameters.get("language", "csharp"))
        
        if not project_path:
            context["action_result"] = {"status": "error", "message": "プロジェクトパスが指定されていません。"}
            return context
            
        abs_project_path = self.ae._safe_join(project_path)
        if not abs_project_path or not os.path.exists(abs_project_path):
            context["action_result"] = {"status": "error", "message": f"プロジェクトパス '{project_path}' が見つかりません。"}
            return context

        try:
            options = parameters.get("options", {"output_formats": ["json", "text"]})
            result = self.ae.coverage_analyzer.analyze_project(abs_project_path, language, options)
            
            if result["status"] == "success":
                gap_analysis = result.get("gap_analysis", {})
                uncovered_files = gap_analysis.get("uncovered_files", [])
                missing_scenarios = gap_analysis.get("missing_test_scenarios", [])
                
                message = f"プロジェクト '{project_path}' のカバレッジギャップ分析が完了しました。\n\n"
                
                if uncovered_files:
                    message += f"未カバー領域: {len(uncovered_files)}ファイル\n"
                    for file_info in uncovered_files[:3]:
                        message += f"- {file_info.get('file', '')}: {len(file_info.get('uncovered_methods', []))}個の未カバーメソッド\n"
                    
                    if len(uncovered_files) > 3:
                        message += f"... 他 {len(uncovered_files) - 3} ファイル\n"
                else:
                    message += "未カバー領域は見つかりませんでした。\n"
                
                if missing_scenarios:
                    message += f"\n不足テストシナリオ: {len(missing_scenarios)}個\n"
                    for scenario in missing_scenarios[:3]:
                        message += f"- {scenario.get('target_method', '')}: {scenario.get('scenario', '')}\n"
                    
                    if len(missing_scenarios) > 3:
                        message += f"... 他 {len(missing_scenarios) - 3} シナリオ\n"
                
                recommendations = result.get("recommendations", [])
                if recommendations:
                    high_priority = len([r for r in recommendations if r.get("priority") == "high"])
                    message += f"\n改善提案: {len(recommendations)}件 (高優先度: {high_priority}件)\n"
                
                context["action_result"] = {
                    "status": "success",
                    "message": message,
                    "gap_analysis": gap_analysis,
                    "recommendations": recommendations
                }
            else:
                context["action_result"] = {"status": "error", "message": result.get("message", "ギャップ分析に失敗しました。")}
                
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"ギャップ分析中にエラーが発生しました: {e}")
            
        return context

    def generate_coverage_report(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """カバレッジレポートを生成する"""
        project_path = self.ae._get_entity_value(parameters.get("project_path"))
        language = self.ae._get_entity_value(parameters.get("language", "csharp"))
        output_formats = self.ae._get_entity_value(parameters.get("output_formats", "json,html,text"))
        
        if not project_path:
            context["action_result"] = {"status": "error", "message": "プロジェクトパスが指定されていません。"}
            return context
            
        abs_project_path = self.ae._safe_join(project_path)
        if not abs_project_path or not os.path.exists(abs_project_path):
            context["action_result"] = {"status": "error", "message": f"プロジェクトパス '{project_path}' が見つかりません。"}
            return context

        try:
            if isinstance(output_formats, str):
                formats_list = [f.strip() for f in output_formats.split(",")]
            else:
                formats_list = output_formats if isinstance(output_formats, list) else ["json", "html", "text"]
            
            options = parameters.get("options", {})
            options["output_formats"] = formats_list
            
            result = self.ae.coverage_analyzer.analyze_project(abs_project_path, language, options)
            
            if result["status"] == "success":
                reports = result.get("reports", {})
                summary = result.get("coverage_summary", {})
                
                message = f"プロジェクト '{project_path}' のカバレッジレポートを生成しました。\n\n"
                message += f"カバレッジサマリー:\n"
                message += f"- ライン カバレッジ: {summary.get('line_coverage', 0):.1f}%\n"
                
                if "branch_coverage" in summary:
                    message += f"- ブランチ カバレッジ: {summary['branch_coverage']:.1f}%\n"
                if "method_coverage" in summary:
                    message += f"- メソッド カバレッジ: {summary['method_coverage']:.1f}%\n"
                
                message += f"\n生成されたレポート:\n"
                for report_type, report_path in reports.items():
                    if report_type == "text_summary":
                        message += f"- サマリー: {report_path}\n"
                    else:
                        message += f"- {report_type.upper()}レポート: {report_path}\n"
                
                quality_metrics = result.get("quality_metrics", {})
                if quality_metrics:
                    message += f"\n品質メトリクス:\n"
                    message += f"- 品質スコア: {quality_metrics.get('quality_score', 0):.1f}/10\n"
                    message += f"- 技術的負債: {quality_metrics.get('technical_debt', 'unknown')}\n"
                
                context["action_result"] = {
                    "status": "success",
                    "message": message,
                    "reports": reports,
                    "coverage_summary": summary,
                    "quality_metrics": quality_metrics
                }
            else:
                context["action_result"] = {"status": "error", "message": result.get("message", "レポート生成に失敗しました。")}
                
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"レポート生成中にエラーが発生しました: {e}")
            
        return context
