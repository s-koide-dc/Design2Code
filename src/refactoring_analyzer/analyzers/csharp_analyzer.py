# -*- coding: utf-8 -*-
# src/refactoring_analyzer/csharp_analyzer.py

import os
from typing import Dict, List, Any, Optional
from .base_analyzer import BaseRefactoringAnalyzer
from ..detectors import LongMethodDetector, DuplicateCodeDetector, ComplexConditionDetector, GodClassDetector

class CSharpRefactoringAnalyzer(BaseRefactoringAnalyzer):
    """C# Roslynベースのリファクタリング分析器"""

    def __init__(self, config: Dict[str, Any], action_executor=None):
        super().__init__(config)
        self.action_executor = action_executor

    def _initialize_detectors(self) -> Dict[str, Any]:
        """C#用検出器を初期化"""
        thresholds = self.config.get("smell_thresholds", {})
        return {
            "long_method": LongMethodDetector(thresholds),
            "duplicate_code": DuplicateCodeDetector(thresholds),
            "complex_condition": ComplexConditionDetector(thresholds),
            "god_class": GodClassDetector(thresholds)
        }
    
    def detect_smells(self, project_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """C#プロジェクトのコードスメルを検出"""
        if not self.action_executor:
            return {"status": "error", "message": "ActionExecutorが設定されていません。C#解析には必須です。"}
        
        try:
            # MyRoslynAnalyzerを実行し、解析結果を取得
            dummy_context = {"session_id": "dummy", "analysis": {}, "plan": {}}
            analysis_parameters = {"filename": project_path}
            
            roslyn_result = self.action_executor._analyze_csharp(dummy_context, analysis_parameters)
            
            if roslyn_result["action_result"]["status"] != "success":
                return {"status": "error", "message": f"MyRoslynAnalyzerの実行に失敗しました: {roslyn_result['action_result']['message']}"}
            
            roslyn_analysis = roslyn_result["action_result"]["analysis"]
            
            # 検出器を初期化
            smell_detectors = self._initialize_detectors()
            
            code_smells = []
            files_analyzed_count = len(set(obj.get("filePath") for obj in roslyn_analysis["manifest"].get("objects", [])))
            
            manifest_objects_from_roslyn = {obj["id"]: obj for obj in roslyn_analysis["manifest"].get("objects", [])}
            details_by_id = roslyn_analysis["details_by_id"]

            for obj_id, detail in details_by_id.items():
                if not detail:
                    continue
                
                manifest_entry = manifest_objects_from_roslyn.get(obj_id, {})
                if not manifest_entry:
                    continue
                
                if detail["type"] == "Class":
                    code_smells.extend(smell_detectors["god_class"].detect_roslyn(
                        detail, manifest_entry, roslyn_analysis, project_path
                    ))
                
                elif detail["type"] == "Method":
                    code_smells.extend(smell_detectors["long_method"].detect_roslyn(
                        detail, manifest_entry, roslyn_analysis, project_path
                    ))
                    code_smells.extend(smell_detectors["complex_condition"].detect_roslyn(
                        detail, manifest_entry, roslyn_analysis, project_path
                    ))
                    code_smells.extend(smell_detectors["duplicate_code"].detect_roslyn(
                        detail, manifest_entry, roslyn_analysis, project_path
                    ))
                
            return {
                "status": "success",
                "code_smells": code_smells,
                "files_analyzed": files_analyzed_count,
                "roslyn_analysis": roslyn_analysis
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"C#スメル検出エラー: {str(e)}"
            }
            # TODO: Implement Logic: **結果の統合**: 検出されたすべてのスメルを一つのリストに集約して返す。
