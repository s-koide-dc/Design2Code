# -*- coding: utf-8 -*-
# src/refactoring_analyzer/metrics/metrics_calculator.py

import os
import math
from typing import Dict, List, Any, Optional

class QualityMetricsCalculator:
    """品質メトリクス計算機"""
    
    def __init__(self, language: str):
        self.language = language
    
    def calculate(self, project_path: str, code_smells: List[Dict[str, Any]], roslyn_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """プロジェクトの品質メトリクスを計算"""
        try:
            overall_score = self._calculate_overall_score(code_smells, roslyn_data)
            maintainability_index = self._calculate_maintainability_index(roslyn_data)
            technical_debt = self._estimate_technical_debt(code_smells)
            duplication_percentage = self._calculate_code_duplication_percentage(code_smells)
            improvement_potential = max(0.0, 10.0 - overall_score)
            
            return {
                "overall_score": overall_score,
                "maintainability_index": maintainability_index,
                "technical_debt_hours": technical_debt,
                "code_duplication_percentage": duplication_percentage,
                "improvement_potential": improvement_potential,
                "rating": self._determine_rating(overall_score)
            }
        except Exception:
            return {
                "overall_score": 0,
                "maintainability_index": 0,
                "technical_debt_hours": 0,
                "code_duplication_percentage": 0.0,
                "improvement_potential": 0.0,
                "rating": "Unknown"
            }

    def _calculate_overall_score(self, code_smells: List[Dict[str, Any]], roslyn_data: Optional[Dict[str, Any]]) -> float:
        """総合品質スコアを計算（10点満点）"""
        base_score = 10.0
        
        # スメルの重み付け減点
        deductions = {
            "high": 1.0,
            "medium": 0.4,
            "low": 0.1
        }
        
        total_deduction = 0
        for smell in code_smells:
            severity = smell.get("severity", "medium")
            total_deduction += deductions.get(severity, 0.4)
            
        # Roslynデータ（CC等）がある場合はそれも考慮
        if roslyn_data and "project_metrics" in roslyn_data:
            metrics = roslyn_data["project_metrics"]
            avg_cc = metrics.get("averageCyclomaticComplexity", 1.0)
            if avg_cc > 5.0:
                total_deduction += (avg_cc - 5.0) * 0.5
                
        return max(0.0, base_score - total_deduction)

    def _calculate_maintainability_index(self, roslyn_data: Optional[Dict[str, Any]]) -> int:
        """保守性指数を計算 (0-100)"""
        # 簡易的な計算式
        if roslyn_data and "project_metrics" in roslyn_data:
            metrics = roslyn_data["project_metrics"]
            avg_cc = metrics.get("averageCyclomaticComplexity", 1.0)
            # CCが低いほど保守性が高い
            return max(0, min(100, int(100 - (avg_cc * 5))))
        return 75 # デフォルト

    def _estimate_technical_debt(self, code_smells: List[Dict[str, Any]]) -> float:
        """技術的負債（修正にかかる推定時間/h）を推計"""
        # 難易度別工数（時間）
        effort = {
            "high": 4.0,
            "medium": 1.5,
            "low": 0.5
        }
        
        total_effort = 0
        for smell in code_smells:
            severity = smell.get("severity", "medium")
            total_effort += effort.get(severity, 1.5)
            
        return total_effort

    def _calculate_code_duplication_percentage(self, code_smells: List[Dict[str, Any]]) -> float:
        """重複コード率の簡易推計（0-100）"""
        duplicate_smells = [s for s in code_smells if s.get("type") == "duplicate_code"]
        if not duplicate_smells:
            return 0.0
        occurrences = 0
        for smell in duplicate_smells:
            metrics = smell.get("metrics", {})
            occ = metrics.get("occurrences")
            if occ is None:
                occ = metrics.get("occurrences_count")
            if occ is None:
                occ = 2
            try:
                occurrences += int(occ)
            except Exception:
                occurrences += 2
        # 1件あたり 2.5% として上限 100%
        return min(100.0, occurrences * 2.5)

    def _estimate_fix_time(self, smell: Dict[str, Any]) -> float:
        """単一スメルの修正時間見積もり（時間）"""
        base = 1.0
        smell_type = (smell.get("type") or "").lower()
        if smell_type == "long_method":
            base = 3.0
        elif smell_type == "duplicate_code":
            base = 2.0
        elif smell_type == "complex_condition":
            base = 1.5
        elif smell_type == "god_class":
            base = 5.0
        severity = (smell.get("severity") or "medium").lower()
        multiplier = 1.0
        if severity == "high":
            multiplier = 1.5
        elif severity == "low":
            multiplier = 0.7
        return base * multiplier

    def _determine_rating(self, score: float) -> str:
        """スコアからレーティングを決定"""
        if score >= 9.0: return "A"
        elif score >= 7.5: return "B"
        elif score >= 6.0: return "C"
        elif score >= 4.0: return "D"
        else: return "E"
