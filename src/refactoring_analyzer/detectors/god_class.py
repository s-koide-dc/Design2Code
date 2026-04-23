# -*- coding: utf-8 -*-
# src/refactoring_analyzer/detectors/god_class.py

import os
import re
from typing import Dict, List, Any
from .base_detector import BaseSmellDetector

class GodClassDetector(BaseSmellDetector):
    """神クラス検出器"""
    
    def detect(self, file_path: str, content: str, project_root: str) -> List[Dict[str, Any]]:
        """神クラス（責任過多クラス）を検出"""
        smells = []
        lines = content.split('\n')
        
        # クラス定義を検索
        class_pattern = r'^\s*(public|internal)?\s*class\s+(\w+)'
        
        for i, line in enumerate(lines):
            class_match = re.search(class_pattern, line)
            if class_match:
                class_name = class_match.group(2)
                class_metrics = self._analyze_class_metrics(lines, i)
                
                threshold = self.thresholds.get("class_line_count", 300)
                
                if class_metrics["line_count"] > threshold:
                    rel_path = os.path.relpath(file_path, project_root)
                    smells.append({
                        "type": "god_class",
                        "severity": "high",
                        "file": rel_path,
                        "class": class_name,
                        "line_start": i + 1,
                        "metrics": class_metrics,
                        "description": f"クラス '{class_name}' が大きすぎます（{class_metrics['line_count']}行）。",
                        "impact": "単一責任原則に違反し、保守が困難になります。"
                    })
        
        return smells
    
    def _analyze_class_metrics(self, lines: List[str], start_index: int) -> Dict[str, Any]:
        """クラスのメトリクスを分析"""
        brace_count = 0
        line_count = 0
        method_count = 0
        
        for i in range(start_index, len(lines)):
            line = lines[i]
            brace_count += line.count('{') - line.count('}')
            line_count += 1
            
            # メソッド数をカウント
            if re.search(r'^\s*(public|private|protected)\s+\w+\s+\w+\s*\(', line):
                method_count += 1
            
            if brace_count == 0 and i > start_index:
                break
        
        return {
            "line_count": line_count,
            "method_count": method_count,
            "estimated_complexity": method_count * 2
        }

    def detect_roslyn(self, object_details: Dict[str, Any], manifest_entry: Dict[str, Any], 
                      roslyn_analysis_results: Dict[str, Any], project_root: str) -> List[Dict[str, Any]]:
        """Roslyn解析結果から神クラス（責任過多クラス）を検出"""
        smells = []
        
        if object_details.get("type") in ["Class", "Struct"]:
            class_name = object_details.get("fullName")
            class_start_line = object_details.get("startLine")
            class_end_line = object_details.get("endLine")
            
            method_count = len(object_details.get("methods", []))

            # Use the lineCount directly from Roslyn metrics
            class_line_count = object_details.get("metrics", {}).get("lineCount", 0)

            threshold_line_count = self.thresholds.get("class_line_count", 300)
            threshold_method_count = self.thresholds.get("god_class_method_count", 15)

            is_god_class = False
            description_parts = []
            
            if class_line_count > threshold_line_count:
                is_god_class = True
                description_parts.append(f"クラスが大きすぎます（{class_line_count}行）。推奨は{threshold_line_count}行以下です。")
            
            if method_count > threshold_method_count:
                is_god_class = True
                description_parts.append(f"メソッドが多すぎます（{method_count}個）。推奨は{threshold_method_count}個以下です。")
            
            if is_god_class:
                rel_file_path = os.path.relpath(manifest_entry["filePath"], project_root)
                smells.append({
                    "type": "god_class",
                    "severity": "high",
                    "file": rel_file_path,
                    "class": class_name,
                    "line_start": class_start_line,
                    "line_end": class_end_line,
                    "metrics": {
                        "line_count": class_line_count,
                        "method_count": method_count,
                        "class_line_threshold": threshold_line_count,
                        "method_count_threshold": threshold_method_count
                    },
                    "description": " ".join(description_parts) or "クラスが多くの責任を持ちすぎている可能性があります。",
                    "impact": "単一責任原則に違反し、保守が困難になります。"
                })
        
        return smells
        # TODO: Implement Logic: クラス定義を特定し、波括弧のバランスからクラスの終端を判定。
        # TODO: Implement Logic: クラス内の行数とメソッド数をカウント。
        # TODO: Implement Logic: **判定基準**:
            # TODO: Implement Logic: 行数が 300行 を超える、または メソッド数が 15個 を超える場合に「神クラス」として検出。
