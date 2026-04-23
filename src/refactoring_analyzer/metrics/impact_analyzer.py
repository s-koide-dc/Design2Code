# -*- coding: utf-8 -*-
# src/refactoring_analyzer/impact_analyzer.py

import os
from typing import Dict, List, Any, Optional

class ImpactScopeAnalyzer:
    """影響範囲分析器"""
    
    def __init__(self, language: str, roslyn_analysis_results: Optional[Dict[str, Any]] = None):
        self.language = language
        self.roslyn_analysis_results = roslyn_analysis_results
        self.manifest = roslyn_analysis_results.get("manifest", {}).get("objects", []) if roslyn_analysis_results else []
        self.details_by_id = roslyn_analysis_results.get("details_by_id", {}) if roslyn_analysis_results else {}
        self.all_roslyn_objects_by_id = {obj["id"]: obj for obj in self.manifest}
    
    def analyze(self, suggestions: List[Dict[str, Any]], project_path: str) -> Dict[str, Any]:
        """影響範囲を分析"""
        affected_files = set()
        affected_classes = set()
        affected_methods = set()
        total_dependencies = 0
        
        for suggestion in suggestions:
            target = suggestion.get("target", {})
            target_file = target.get("file")
            target_class = target.get("class")
            target_method = target.get("method")

            if target_file:
                affected_files.add(target_file)
            if target_class:
                affected_classes.add(target_class)
            if target_method:
                affected_methods.add(target_method)

            if self.language == "csharp" and self.roslyn_analysis_results:
                # Roslyn解析結果からより詳細な影響範囲を分析
                # 現在のRoslynベースの実装は、メソッドの呼び出し元 (calledBy)、呼び出し先 (calls)、
                # プロパティ/フィールドへのアクセス (accesses)、プロパティ/フィールドへのアクセス元 (accessedBy)、
                # およびクラスレベルの依存関係 (dependencies) を包括的にトラバースします。
                # 真に「完全な」依存グラフ解析のためには、インターフェースの実装、ジェネリック型の使用など、
                # さらなる種類の依存関係を考慮する強化が必要となる場合があります。
                
                # 提案のターゲットから直接影響を受けるオブジェクトを特定
                initial_affected_ids = set()
                for obj_id, detail in self.details_by_id.items():
                    rel_file_path = os.path.relpath(detail["filePath"], project_path)
                    
                    if target_file and rel_file_path == target_file:
                        if target_class and detail.get("fullName") == target_class:
                            initial_affected_ids.add(obj_id)
                        if target_method and detail.get("type") == "Method" and detail.get("fullName") == target_method:
                            initial_affected_ids.add(obj_id)

                # 依存グラフを辿って間接的な影響範囲を特定
                queue = list(initial_affected_ids)
                visited = set(initial_affected_ids)

                while queue:
                    current_id = queue.pop(0)
                    current_detail = self.details_by_id.get(current_id)

                    if not current_detail:
                        continue
                    
                    if current_detail["type"] == "Method":
                        # メソッドが呼び出しているメソッドを追加
                        for dep_info in current_detail.get("calls", []):
                            if dep_info["id"] not in visited:
                                visited.add(dep_info["id"])
                                queue.append(dep_info["id"])
                        # メソッドを呼び出しているメソッドを追加 (逆方向)
                        for dep_info in current_detail.get("calledBy", []):
                            if dep_info["id"] not in visited:
                                visited.add(dep_info["id"])
                                queue.append(dep_info["id"])
                        # メソッドがアクセスしているプロパティ/フィールドを追加
                        for dep_info in current_detail.get("accesses", []):
                            if dep_info["id"] not in visited:
                                visited.add(dep_info["id"])
                                queue.append(dep_info["id"])
                    elif current_detail["type"] in ["Class", "Struct"]:
                        # クラス内のメソッドを処理
                        for method_in_class in current_detail.get("methods", []):
                            for dep_info in method_in_class.get("calls", []):
                                if dep_info["id"] not in visited:
                                    visited.add(dep_info["id"])
                                    queue.append(dep_info["id"])
                            for dep_info in method_in_class.get("calledBy", []):
                                if dep_info["id"] not in visited:
                                    visited.add(dep_info["id"])
                                    queue.append(dep_info["id"])
                            for dep_info in method_in_class.get("accesses", []):
                                if dep_info["id"] not in visited:
                                    visited.add(dep_info["id"])
                                    queue.append(dep_info["id"])
                        # クラス内のプロパティを処理
                        for prop_in_class in current_detail.get("properties", []):
                            for dep_info in prop_in_class.get("accessedBy", []):
                                if dep_info["id"] not in visited:
                                    visited.add(dep_info["id"])
                                    queue.append(dep_info["id"])
                        # クラスレベルの依存関係も考慮
                        for dep_info in current_detail.get("dependencies", []):
                            if dep_info["id"] not in visited:
                                visited.add(dep_info["id"])
                                queue.append(dep_info["id"])

                total_dependencies = len(visited)
                
                # 影響範囲のファイル、クラス、メソッドを収集
                for id_in_visited in visited:
                    detail = self.details_by_id.get(id_in_visited)
                    if detail:
                        rel_file_path = os.path.relpath(detail["filePath"], project_path)
                        affected_files.add(rel_file_path)
                        
                        if detail["type"] in ["Class", "Struct"]:
                            affected_classes.add(detail["fullName"])
                        elif detail["type"] == "Method":
                            affected_methods.add(detail["fullName"])

        risk_level = "low"
        estimated_test_impact = "low"

        if len(affected_files) > 5 or total_dependencies > 10:
            risk_level = "high"
            estimated_test_impact = "high"
        elif len(affected_files) > 2 or total_dependencies > 3:
            risk_level = "medium"
            estimated_test_impact = "medium"
        
        return {
            "total_affected_files": len(affected_files),
            "affected_files": list(affected_files),
            "total_affected_classes": len(affected_classes),
            "affected_classes": list(affected_classes),
            "total_affected_methods": len(affected_methods),
            "affected_methods": list(affected_methods),
            "total_dependencies_identified": total_dependencies,
            "estimated_test_impact": estimated_test_impact,
            "risk_level": risk_level
        }
        # TODO: Implement Logic: 幅優先探索（BFS）を用いて、依存関係グラフを再帰的に辿り、波及範囲を特定。
        # TODO: Implement Logic: **直接的影響の特定**: 提案のターゲットとなっているファイル、クラス、メソッドを収集。
        # TODO: Implement Logic: **間接的影響のトラバース (C#)**:
            # TODO: Implement Logic: **リスク評価**:
                # TODO: Implement Logic: 影響を受けるファイル数（>5）や依存関係数（>10）に基づき、リスクレベルを判定。
