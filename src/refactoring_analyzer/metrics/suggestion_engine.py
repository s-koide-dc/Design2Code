# -*- coding: utf-8 -*-
# src/refactoring_analyzer/suggestion_engine.py

from typing import Dict, List, Any

class RefactoringSuggestionEngine:
    """リファクタリング提案エンジン"""
    
    def __init__(self, language: str, config: Dict[str, Any]):
        self.language = language
        self.config = config
    
    def generate_suggestions(self, code_smells: List[Dict[str, Any]], options: Dict[str, Any]) -> List[Dict[str, Any]]:
        """リファクタリング提案を生成"""
        suggestions = []
        
        for smell in code_smells:
            smell_suggestions = self._generate_suggestions_for_smell(smell)
            suggestions.extend(smell_suggestions)
        
        # 優先度でソート
        suggestions.sort(key=lambda x: self._get_priority_score(x["priority"]), reverse=True)
        
        # 最大提案数の制限
        max_suggestions = options.get("max_suggestions", 10)
        return suggestions[:max_suggestions]
    
    def _generate_suggestions_for_smell(self, smell: Dict[str, Any]) -> List[Dict[str, Any]]:
        """特定のスメルに対する提案を生成"""
        smell_type = smell["type"]
        
        if smell_type == "long_method":
            return self._suggest_extract_method(smell)
        elif smell_type == "duplicate_code":
            return self._suggest_extract_common_method(smell)
        elif smell_type == "complex_condition":
            return self._suggest_simplify_condition(smell)
        elif smell_type == "god_class":
            return self._suggest_split_class(smell)
        
        return []
    
    def _suggest_extract_method(self, smell: Dict[str, Any]) -> List[Dict[str, Any]]:
        """メソッド抽出の提案"""
        return [{
            "id": f"extract_method_{smell['file']}_{smell['line_start']}",
            "type": "extract_method",
            "priority": "high",
            "target": {
                "file": smell["file"],
                "method": smell.get("method"),
                "lines": f"{smell['line_start']}-{smell['line_end']}"
            },
            "suggestion": {
                "new_method_name": f"Extract{smell.get('method', 'Method')}Logic",
                "description": f"メソッド '{smell.get('method')}' の一部を別メソッドに抽出",
                "estimated_effort": "15-30分",
                "safety_level": "safe"
            },
            "code_example": {
                "before": f"// 長いメソッド ({smell['metrics']['line_count']}行)",
                "after": "// 抽出されたメソッド + 元のメソッド（簡潔化）"
            },
            "auto_fixable": False,
            "impact_analysis": {
                "affected_files": [smell["file"]],
                "test_impact": "新しいメソッドのテスト追加が必要",
                "coverage_change": "新メソッドのテスト追加推奨"
            }
        }]
    
    def _suggest_extract_common_method(self, smell: Dict[str, Any]) -> List[Dict[str, Any]]:
        """共通メソッド抽出の提案"""
        return [{
            "id": f"extract_common_{smell['file']}_{smell['lines'][0] if 'lines' in smell else 0}",
            "type": "extract_common_method",
            "priority": "medium",
            "target": {
                "file": smell["file"],
                "lines": smell.get("lines")
            },
            "suggestion": {
                "new_method_name": "ExtractedCommonLogic",
                "description": f"重複コード（{smell['metrics']['occurrences_count'] if 'occurrences_count' in smell['metrics'] else smell['metrics'].get('occurrences', 0)}箇所）を共通メソッドに抽出",
                "estimated_effort": "20-40分",
                "safety_level": "medium"
            },
            "auto_fixable": False,
            "impact_analysis": {
                "affected_files": [smell["file"]],
                "test_impact": "共通メソッドのテスト追加が必要"
            }
        }]
    
    def _suggest_simplify_condition(self, smell: Dict[str, Any]) -> List[Dict[str, Any]]:
        """条件式簡素化の提案"""
        return [{
            "id": f"simplify_condition_{smell['file']}_{smell.get('line', smell.get('line_start', 0))}",
            "type": "simplify_condition",
            "priority": "medium",
            "target": {
                "file": smell["file"],
                "line": smell.get("line", smell.get("line_start"))
            },
            "suggestion": {
                "description": "複雑な条件式を複数の変数に分割",
                "estimated_effort": "10-20分",
                "safety_level": "safe"
            },
            "code_example": {
                "before": smell.get("content", ""),
                "after": "// 条件を複数の変数に分割した例"
            },
            "auto_fixable": False
        }]
    
    def _suggest_split_class(self, smell: Dict[str, Any]) -> List[Dict[str, Any]]:
        """クラス分割の提案"""
        return [{
            "id": f"split_class_{smell['file']}_{smell.get('class')}",
            "type": "split_class",
            "priority": "high",
            "target": {
                "file": smell["file"],
                "class": smell.get("class")
            },
            "suggestion": {
                "description": f"クラス '{smell.get('class')}' を責任ごとに複数のクラスに分割",
                "estimated_effort": "2-4時間",
                "safety_level": "complex"
            },
            "auto_fixable": False,
            "impact_analysis": {
                "affected_files": [smell["file"]],
                "test_impact": "大幅なテスト修正が必要",
                "coverage_change": "新しいクラス構造に応じたテスト再設計"
            }
        }]
    
    def _get_priority_score(self, priority: str) -> int:
        """優先度スコアを取得"""
        priority_scores = {"high": 3, "medium": 2, "low": 1}
        return priority_scores.get(priority, 1)
        # TODO: Implement Logic: **スメル別の戦略立案**:
            # TODO: Implement Logic: **ランキング**: 重要度と優先度に基づいてソートし、上位件数に絞り込み。
            # TODO: Implement Logic: **影響分析の付与**: 各提案に対し、テストへの影響範囲や安全レベルを付記。
