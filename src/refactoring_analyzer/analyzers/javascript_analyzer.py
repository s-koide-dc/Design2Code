# -*- coding: utf-8 -*-
# src/refactoring_analyzer/javascript_analyzer.py

import os
from typing import Dict, List, Any
from .base_analyzer import BaseRefactoringAnalyzer
from ..detectors import LongMethodDetector, ComplexConditionDetector

class JavaScriptRefactoringAnalyzer(BaseRefactoringAnalyzer):
    """JavaScript ESLintベースのリファクタリング分析器"""
    
    def _initialize_detectors(self) -> Dict[str, Any]:
        """JavaScript用検出器を初期化"""
        thresholds = self.config.get("smell_thresholds", {})
        return {
            "long_method": LongMethodDetector(thresholds),
            "complex_condition": ComplexConditionDetector(thresholds)
        }
    
    def detect_smells(self, project_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """JavaScriptプロジェクトのコードスメルを検出"""
        try:
            code_smells = []
            js_files = self._find_js_files(project_path)
            
            for js_file in js_files:
                file_smells = self._analyze_file(js_file, project_path)
                code_smells.extend(file_smells)
            
            return {
                "status": "success",
                "code_smells": code_smells,
                "files_analyzed": len(js_files)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"JavaScriptスメル検出エラー: {str(e)}"
            }
    
    def _find_js_files(self, project_path: str) -> List[str]:
        """JavaScriptファイルを検索"""
        js_files = []
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in ['node_modules', '.git', 'dist', 'build']]
            for file in files:
                if file.endswith(('.js', '.jsx', '.ts', '.tsx')) and not file.endswith('.test.js'):
                    js_files.append(os.path.join(root, file))
        return js_files
    
    def _analyze_file(self, file_path: str, project_root: str) -> List[Dict[str, Any]]:
        """単一ファイルを分析"""
        return self._safe_analyze_file(file_path, project_root)
