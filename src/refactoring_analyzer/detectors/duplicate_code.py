# -*- coding: utf-8 -*-
# src/refactoring_analyzer/detectors/duplicate_code.py

import os
from collections import defaultdict
from typing import Dict, List, Any
from .base_detector import BaseSmellDetector

class DuplicateCodeDetector(BaseSmellDetector):
    """重複コード検出器"""
    
    def detect(self, file_path: str, content: str, project_root: str) -> List[Dict[str, Any]]:
        """重複コードを検出"""
        smells = []
        
        # 簡単な実装：同じ行が複数回出現する場合を検出
        lines = [line.strip() for line in content.split('\n') if line.strip() and not line.strip().startswith('//')]
        line_counts = defaultdict(list)
        
        for i, line in enumerate(lines):
            if len(line) > 10:  # 短い行は除外
                line_counts[line].append(i + 1)
        
        for line, occurrences in line_counts.items():
            if len(occurrences) >= 3:  # 3回以上の重複
                rel_path = os.path.relpath(file_path, project_root)
                smells.append({
                    "type": "duplicate_code",
                    "severity": "medium",
                    "file": rel_path,
                    "lines": occurrences,
                    "content": line[:50] + "..." if len(line) > 50 else line,
                    "metrics": {
                        "occurrences": len(occurrences),
                        "line_length": len(line)
                    },
                    "description": f"重複コードが{len(occurrences)}箇所で発見されました。",
                    "impact": "保守性が低下し、バグの原因となる可能性があります。"
                })
        
        return smells

    def detect_roslyn(self, object_details: Dict[str, Any], manifest_entry: Dict[str, Any], 
                      roslyn_analysis_results: Dict[str, Any], project_root: str) -> List[Dict[str, Any]]:
        """Roslyn解析結果から重複コードを検出"""
        smells = []
        
        if object_details.get("type") == "Method":
            method_name = object_details.get("name")
            method_id = object_details.get("id")
            body_hash = object_details.get("metrics", {}).get("bodyHash")
            
            if not body_hash:
                return []
            
            all_methods_with_same_hash = []
            for other_obj_id, other_detail in roslyn_analysis_results["details_by_id"].items():
                if other_detail.get("type") == "Method":
                    other_body_hash = other_detail.get("metrics", {}).get("bodyHash")
                    if body_hash == other_body_hash:
                        all_methods_with_same_hash.append(other_detail)
            
            all_methods_with_same_hash.sort(key=lambda x: x["id"])

            if len(all_methods_with_same_hash) > 1 and object_details["id"] == all_methods_with_same_hash[0]["id"]:
                all_occurrences = []
                for m in all_methods_with_same_hash:
                    all_occurrences.append({
                        "file": os.path.relpath(m["filePath"], project_root),
                        "method": m["name"],
                        "line_start": m["startLine"],
                        "line_end": m["endLine"]
                    })
                
                smells.append({
                    "type": "duplicate_code",
                    "severity": "medium",
                    "file": os.path.relpath(manifest_entry["filePath"], project_root),
                    "method": method_name,
                    "body_hash": body_hash,
                    "occurrences": all_occurrences,
                    "metrics": {
                        "occurrences_count": len(all_occurrences),
                        "body_hash": body_hash
                    },
                    "description": f"メソッド '{method_name}' のコードボディが{len(all_occurrences)}箇所で重複しています。",
                    "impact": "保守性が低下し、バグの原因となる可能性があります。"
                })
        
        return smells
        # TODO: Implement Logic: 空行とコメントを除いた各行をトークン化。
        # TODO: Implement Logic: 10文字以上の行が 3回以上 出現する場合を「重複」とみなして抽出。
        # TODO: Implement Logic: **結果の集約**: 重複している箇所（ファイル名、メソッド名、行番号）をリスト化して報告。
