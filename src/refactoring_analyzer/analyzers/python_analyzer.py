# -*- coding: utf-8 -*-
# src/refactoring_analyzer/python_analyzer.py

import os
from typing import Dict, List, Any
from .base_analyzer import BaseRefactoringAnalyzer
from ..detectors import LongMethodDetector, DuplicateCodeDetector, ComplexConditionDetector

class PythonRefactoringAnalyzer(BaseRefactoringAnalyzer):
    """Python ASTベースのリファクタリング分析器"""
    
    def _initialize_detectors(self) -> Dict[str, Any]:
        """Python用検出器を初期化"""
        thresholds = self.config.get("smell_thresholds", {})
        return {
            "long_method": LongMethodDetector(thresholds),
            "duplicate_code": DuplicateCodeDetector(thresholds),
            "complex_condition": ComplexConditionDetector(thresholds)
        }
    
    def detect_smells(self, project_path: str, options: Dict[str, Any]) -> Dict[str, Any]:
        """Pythonプロジェクトのコードスメルを検出"""
        try:
            code_smells = []
            py_files = self._find_py_files(project_path)
            
            for py_file in py_files:
                file_smells = self._analyze_file(py_file, project_path)
                code_smells.extend(file_smells)
            
            return {
                "status": "success",
                "code_smells": code_smells,
                "files_analyzed": len(py_files)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"Pythonスメル検出エラー: {str(e)}"
            }
    
    def _find_py_files(self, project_path: str) -> List[str]:
        """Pythonファイルを検索"""
        py_files = []
        for root, dirs, files in os.walk(project_path):
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'venv', '.venv']]
            for file in files:
                if file.endswith('.py') and not file.startswith('test_'):
                    py_files.append(os.path.join(root, file))
        return py_files
    
    def _analyze_file(self, file_path: str, project_root: str) -> List[Dict[str, Any]]:
        """単一ファイルを分析"""
        return self._safe_analyze_file(file_path, project_root)
