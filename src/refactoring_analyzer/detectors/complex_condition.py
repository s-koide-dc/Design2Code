# -*- coding: utf-8 -*-
# src/refactoring_analyzer/detectors/complex_condition.py

import os
import re
from typing import Dict, List, Any
from .base_detector import BaseSmellDetector

class ComplexConditionDetector(BaseSmellDetector):
    """複雑な条件分岐検出器"""
    
    def detect(self, file_path: str, content: str, project_root: str) -> List[Dict[str, Any]]:
        """複雑な条件分岐を検出"""
        smells = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            # if文の複雑度を簡単にチェック
            if re.search(r'\bif\s*\(', line):
                complexity = self._calculate_condition_complexity(line)
                threshold = self.thresholds.get("cyclomatic_complexity", 6)
                
                if complexity > threshold:
                    rel_path = os.path.relpath(file_path, project_root)
                    smells.append({
                        "type": "complex_condition",
                        "severity": "medium" if complexity <= threshold * 1.5 else "high",
                        "file": rel_path,
                        "line": i + 1,
                        "content": line.strip(),
                        "metrics": {
                            "complexity": complexity,
                            "threshold": threshold
                        },
                        "description": f"条件分岐が複雑すぎます（複雑度: {complexity}）。",
                        "impact": "理解が困難で、バグが発生しやすくなります。"
                    })
        
        return smells
    
    def _calculate_condition_complexity(self, line: str) -> int:
        """条件分岐の複雑度を計算"""
        operators = ['&&', '||', '&', '|', '==', '!=', '<', '>', '<=', '>=']
        complexity = 1
        
        for op in operators:
            complexity += line.count(op)
        
        return complexity

    def detect_roslyn(self, object_details: Dict[str, Any], manifest_entry: Dict[str, Any], 
                      roslyn_analysis_results: Dict[str, Any], project_root: str) -> List[Dict[str, Any]]:
        """Roslyn解析結果から複雑な条件分岐を検出"""
        smells = []

        if object_details.get("type") == "Method":
            method_name = object_details.get("name")
            method_start_line = object_details.get("startLine")
            
            cyclomatic_complexity = object_details.get("metrics", {}).get("cyclomaticComplexity", 0)
            threshold = self.thresholds.get("cyclomatic_complexity", 6)
            
            if cyclomatic_complexity > threshold:
                rel_file_path = os.path.relpath(manifest_entry["filePath"], project_root)
                smells.append({
                    "type": "complex_condition",
                    "severity": "medium" if cyclomatic_complexity <= threshold * 1.5 else "high",
                    "file": rel_file_path,
                    "method": method_name,
                    "line_start": method_start_line,
                    "metrics": {
                        "complexity": cyclomatic_complexity,
                        "threshold": threshold
                    },
                    "description": f"メソッド '{method_name}' の条件分岐が複雑である可能性があります（複雑度: {cyclomatic_complexity}）。",
                    "impact": "理解が困難で、バグが発生しやすくなります。"
                })
        
        return smells
        # TODO: Implement Logic: `if` 文を含む行を抽出。
        # TODO: Implement Logic: **閾値判定**: 複雑度が閾値（デフォルト 6）を超えた場合、スメルとして登録。
