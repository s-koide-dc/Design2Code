# -*- coding: utf-8 -*-
# src/cicd_operations/cicd_operations.py

import os
from typing import Dict, Any

class CICDOperations:
    """CI/CD関連の操作を担当する独立モジュール"""
    
    def __init__(self, action_executor):
        self.ae = action_executor

    def setup_cicd_pipeline(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """CI/CDパイプラインを設定する"""
        project_name = self.ae._get_entity_value(parameters.get("project_name"))
        language = self.ae._get_entity_value(parameters.get("language", "csharp"))
        ci_platform = self.ae._get_entity_value(parameters.get("ci_platform", "github_actions"))
        
        if not project_name:
            context["action_result"] = {
                "status": "error",
                "message": "プロジェクト名が指定されていません。"
            }
            return context
        
        try:
            project_info = {
                "name": project_name,
                "language": language,
                "ci_platform": ci_platform,
                "framework": self.ae._get_entity_value(parameters.get("framework", "net6.0")),
                "test_framework": self.ae._get_entity_value(parameters.get("test_framework", "xunit"))
            }
            
            quality_gates = parameters.get("quality_gates", {})
            if quality_gates:
                project_info["quality_gates"] = quality_gates
            
            result = self.ae.cicd_integrator.generate_pipeline(project_info, {
                "output_formats": ["yaml", "json"]
            })
            
            if result["status"] == "success":
                saved_files = []
                for config_file in result.get("config_files", []):
                    file_path = config_file["path"]
                    file_content = config_file["content"]
                    
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(file_content)
                    
                    saved_files.append(file_path)
                
                context["action_result"] = {
                    "status": "success",
                    "message": f"CI/CDパイプライン設定が完了しました。プラットフォーム: {ci_platform}",
                    "pipeline_config": result["pipeline_config"],
                    "quality_gates": result["quality_gates"],
                    "saved_files": saved_files,
                    "project_info": project_info
                }
            else:
                context["action_result"] = result
            
        except Exception as e:
            context["action_result"] = {
                "status": "error",
                "message": f"CI/CDパイプライン設定中にエラーが発生しました: {str(e)}"
            }
            
            if self.ae.log_manager:
                self.ae.log_manager.log_event("cicd_setup_error", {
                    "project_name": project_name,
                    "language": language,
                    "error": str(e)
                }, "ERROR")
        
        return context
    
    def configure_quality_gates(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """品質ゲートを設定する"""
        language = self.ae._get_entity_value(parameters.get("language", "csharp"))
        
        try:
            quality_config = {}
            
            if "coverage_threshold" in parameters:
                quality_config["test_coverage_threshold"] = float(self.ae._get_entity_value(parameters["coverage_threshold"]))
            
            if "quality_score_threshold" in parameters:
                quality_config["quality_score_threshold"] = float(self.ae._get_entity_value(parameters["quality_score_threshold"]))
            
            if "max_high_priority_smells" in parameters:
                quality_config["max_high_priority_smells"] = int(self.ae._get_entity_value(parameters["max_high_priority_smells"]))
            
            if "max_medium_priority_smells" in parameters:
                quality_config["max_medium_priority_smells"] = int(self.ae._get_entity_value(parameters["max_medium_priority_smells"]))
            
            result = self.ae.cicd_integrator.setup_quality_gates(quality_config, language)
            
            if result["status"] == "success":
                context["action_result"] = {
                    "status": "success",
                    "message": f"品質ゲートが設定されました。言語: {language}",
                    "gates": result["gates"],
                    "total_gates": result["total_gates"],
                    "blocking_gates": result["blocking_gates"],
                    "warning_gates": result["warning_gates"],
                    "language": language
                }
            else:
                context["action_result"] = result
            
        except Exception as e:
            context["action_result"] = {
                "status": "error",
                "message": f"品質ゲート設定中にエラーが発生しました: {str(e)}"
            }
            
            if self.ae.log_manager:
                self.ae.log_manager.log_event("quality_gates_config_error", {
                    "language": language,
                    "error": str(e)
                }, "ERROR")
        
        return context
    
    def generate_cicd_config(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """CI/CD設定ファイルを生成する"""
        project_name = self.ae._get_entity_value(parameters.get("project_name"))
        language = self.ae._get_entity_value(parameters.get("language", "csharp"))
        ci_platform = self.ae._get_entity_value(parameters.get("ci_platform", "github_actions"))
        
        if not project_name:
            context["action_result"] = {
                "status": "error",
                "message": "プロジェクト名が指定されていません。"
            }
            return context
        
        try:
            project_info = {
                "name": project_name,
                "language": language,
                "ci_platform": ci_platform
            }
            
            if "framework" in parameters:
                project_info["framework"] = self.ae._get_entity_value(parameters["framework"])
            
            if "test_framework" in parameters:
                project_info["test_framework"] = self.ae._get_entity_value(parameters["test_framework"])
            
            reports = []
            
            report_dirs = ["test_reports", "coverage_reports", "refactoring_reports"]
            for report_dir in report_dirs:
                report_path = os.path.join(self.ae.workspace_root, report_dir)
                if os.path.exists(report_path):
                    latest_report = self.find_latest_report(report_path)
                    if latest_report:
                        reports.append(latest_report)
            
            integration_result = self.ae.cicd_integrator.integrate_quality_reports(reports, {
                "output_formats": ["json", "html"]
            })
            
            if integration_result["status"] == "success":
                context["action_result"] = {
                    "status": "success",
                    "message": f"CI/CD設定ファイルが生成されました。プロジェクト: {project_name}",
                    "integrated_report": integration_result["integrated_report"],
                    "report_files": integration_result["report_files"],
                    "summary": integration_result["summary"],
                    "project_info": project_info
                }
            else:
                context["action_result"] = integration_result
            
        except Exception as e:
            context["action_result"] = {
                "status": "error",
                "message": f"CI/CD設定ファイル生成中にエラーが発生しました: {str(e)}"
            }
            
            if self.ae.log_manager:
                self.ae.log_manager.log_event("cicd_config_generation_error", {
                    "project_name": project_name,
                    "language": language,
                    "error": str(e)
                }, "ERROR")
        
        return context

    def find_latest_report(self, report_dir: str) -> Dict[str, Any]:
        """最新のレポートファイルを検索"""
        try:
            json_files = []
            for root, dirs, files in os.walk(report_dir):
                for file in files:
                    if file.endswith('.json'):
                        file_path = os.path.join(root, file)
                        json_files.append(file_path)
            
            if json_files:
                # 最新のファイルを取得
                latest_file = max(json_files, key=os.path.getmtime)
                
                # ファイル内容を読み込み
                import json
                with open(latest_file, 'r', encoding='utf-8') as f:
                    report_data = json.load(f)
                
                # レポートタイプを推定
                report_type = "unknown"
                if "code_smells" in report_data:
                    report_type = "refactoring"
                elif "line_coverage" in report_data:
                    report_type = "coverage"
                elif "test_results" in report_data:
                    report_type = "test"
                
                report_data["type"] = report_type
                return report_data
                
        except Exception as e:
            if self.ae.log_manager:
                self.ae.log_manager.log_event("report_search_error", {
                    "report_dir": report_dir,
                    "error": str(e)
                }, "WARNING")
        
        return {}

    def check_quality_gates(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """品質ゲートのチェックを実行する"""
        try:
            from src.cicd_integrator.quality_gate_checker import QualityGateChecker
            checker = QualityGateChecker(self.ae.workspace_root)
            
            # metrics_fileが指定されている場合はそれを使用
            metrics_file = self.ae._get_entity_value(parameters.get("metrics_file"))
            
            # カスタムゲート設定がある場合はそれを使用
            gates_config = parameters.get("gates_config")
            
            result = checker.check_gates(metrics_file=metrics_file, gates_config=gates_config)
            
            # 自律的整合性チェックの実行
            alignment_report = None
            try:
                from src.autonomous_aligner.autonomous_aligner import AutonomousAligner
                # VectorEngineとMorphAnalyzerを注入（実用性向上のためのセマンティック監査用）
                aligner = AutonomousAligner(
                    self.ae.workspace_root, 
                    vector_engine=self.ae.vector_engine,
                    morph_analyzer=self.ae.morph_analyzer
                )
                alignment_report = aligner.align_all_modules()
            except Exception as align_err:
                if self.ae.log_manager:
                    self.ae.log_manager.log_event("alignment_check_error", {"error": str(align_err)}, "WARNING")

            status = "success" if result["overall_status"] in ["passed", "warning"] else "failed"
            if alignment_report:
                # 整合性エラーがある場合、警告または失敗に倒すロジック（オプション）
                inconsistent_modules = [m for m in alignment_report["modules"] if m["status"] == "inconsistent"]
                if inconsistent_modules and status == "success":
                    status = "warning"
                    result["overall_status"] = "warning"

            context["action_result"] = {
                "status": status,
                "message": f"品質ゲートチェック完了: {result['overall_status'].upper()}",
                "overall_status": result["overall_status"],
                "results": result.get("gates", []),
                "summary": result.get("summary", {}),
                "alignment_report": alignment_report
            }
            
        except Exception as e:
            context["action_result"] = {
                "status": "error",
                "message": f"品質ゲートチェック中にエラーが発生しました: {str(e)}"
            }
            
            if self.ae.log_manager:
                self.ae.log_manager.log_event("quality_gate_check_error", {
                    "error": str(e)
                }, "ERROR")
                
        return context
