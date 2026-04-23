# -*- coding: utf-8 -*-
# src/refactoring_operations/refactoring_operations.py

import os
from typing import Dict, Any

class RefactoringOperations:
    """リファクタリング関連の操作を担当する独立モジュール"""
    
    def __init__(self, action_executor):
        self.ae = action_executor

    def analyze_refactoring(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """リファクタリング分析を実行する"""
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
            result = self.ae.refactoring_analyzer.analyze_project(abs_project_path, language, options)
            
            if result["status"] == "success":
                analysis_summary = result.get("analysis_summary", {})
                total_smells = analysis_summary.get("total_smells", 0)
                high_priority = analysis_summary.get("high_priority", 0)
                
                message = f"プロジェクト '{project_path}' のリファクタリング分析が完了しました。\n\n"
                message += f"検出されたコードスメル: {total_smells}件\n"
                message += f"- 高優先度: {high_priority}件\n"
                message += f"- 中優先度: {analysis_summary.get('medium_priority', 0)}件\n"
                message += f"- 低優先度: {analysis_summary.get('low_priority', 0)}件\n"
                
                auto_fixable = analysis_summary.get("auto_fixable", 0)
                if auto_fixable > 0:
                    message += f"\n自動修正可能: {auto_fixable}件\n"
                
                quality_metrics = result.get("quality_metrics", {})
                message += f"\n品質メトリクス:\n"
                message += f"- 総合品質スコア: {quality_metrics.get('overall_score', 0):.1f}/10\n"
                message += f"- 保守性指数: {quality_metrics.get('maintainability_index', 0)}\n"
                message += f"- 技術的負債: {quality_metrics.get('technical_debt_hours', 0):.1f}時間\n"
                
                reports = result.get("reports", {})
                if reports:
                    message += "\n生成されたレポート:\n"
                    for report_type, report_path in reports.items():
                        message += f"- {report_type}: {report_path}\n"
                
                context["action_result"] = {
                    "status": "success",
                    "message": message,
                    "refactoring_result": result
                }
            else:
                context["action_result"] = {"status": "error", "message": result.get("message", "リファクタリング分析に失敗しました。")}
                
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"リファクタリング分析中にエラーが発生しました: {e}")
            
        return context

    def suggest_refactoring(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """リファクタリング提案を生成する"""
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
            options = parameters.get("options", {"max_suggestions": 5})
            result = self.ae.refactoring_analyzer.analyze_project(abs_project_path, language, options)
            
            if result["status"] == "success":
                suggestions = result.get("refactoring_suggestions", [])
                
                message = f"プロジェクト '{project_path}' のリファクタリング提案を生成しました。\n\n"
                
                if suggestions:
                    message += f"提案されたリファクタリング: {len(suggestions)}件\n\n"
                    
                    for i, suggestion in enumerate(suggestions[:3], 1):
                        sug_info = suggestion.get("suggestion", {})
                        message += f"{i}. {suggestion.get('type', 'unknown')} ({suggestion.get('priority', 'medium')}優先度)\n"
                        message += f"   対象: {suggestion.get('target', {}).get('file', 'unknown')}\n"
                        message += f"   内容: {sug_info.get('description', 'No description')}\n"
                        message += f"   見積時間: {sug_info.get('estimated_effort', 'unknown')}\n\n"
                    
                    if len(suggestions) > 3:
                        message += f"... 他 {len(suggestions) - 3} 件の提案\n\n"
                    
                    auto_fixable = [s for s in suggestions if s.get("auto_fixable", False)]
                    if auto_fixable:
                        message += f"自動修正可能な提案: {len(auto_fixable)}件\n"
                else:
                    message += "リファクタリングが必要な問題は見つかりませんでした。\n"
                
                recommendations = result.get("recommendations", [])
                if recommendations:
                    message += "\n推奨事項:\n"
                    for rec in recommendations[:2]:
                        message += f"- {rec.get('description', '')}\n"
                
                context["action_result"] = {
                    "status": "success",
                    "message": message,
                    "suggestions": suggestions,
                    "recommendations": recommendations
                }
            else:
                context["action_result"] = {"status": "error", "message": result.get("message", "リファクタリング提案生成に失敗しました。")}
                
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"リファクタリング提案生成中にエラーが発生しました: {e}")
            
        return context

    def apply_refactoring(self, context: Dict[str, Any], parameters: Dict[str, Any]) -> Dict[str, Any]:
        """リファクタリングを適用する"""
        project_path = self.ae._get_entity_value(parameters.get("project_path"))
        suggestion_id = self.ae._get_entity_value(parameters.get("suggestion_id"))
        
        if not project_path or not suggestion_id:
            context["action_result"] = {"status": "error", "message": "プロジェクトパスまたは提案IDが指定されていません。"}
            return context
            
        abs_project_path = self.ae._safe_join(project_path)
        if not abs_project_path or not os.path.exists(abs_project_path):
            context["action_result"] = {"status": "error", "message": f"プロジェクトパス '{project_path}' が見つかりません。"}
            return context

        try:
            message = f"リファクタリング提案 '{suggestion_id}' の適用準備が完了しました。\n\n"
            message += "現在のバージョンでは、リファクタリングの自動適用はサポートされていません。\n"
            message += "以下の手順で手動で適用してください:\n\n"
            message += "1. 提案されたコード例を参考にしてください\n"
            message += "2. 影響範囲を確認してください\n"
            message += "3. テストを実行して動作を確認してください\n"
            message += "4. 段階的に変更を適用してください\n\n"
            message += "注意: 変更前にバックアップを作成することを強く推奨します。"
            
            context["action_result"] = {
                "status": "success",
                "message": message,
                "suggestion_id": suggestion_id,
                "manual_application_required": True
            }
                
        except Exception as e:
            context["action_result"] = self.ae._handle_exception_with_patterns(e, f"リファクタリング適用中にエラーが発生しました: {e}")
            
        return context