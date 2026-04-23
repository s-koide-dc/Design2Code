# -*- coding: utf-8 -*-
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

@dataclass
class TestFailure:
    """テスト失敗情報を表すデータクラス"""
    test_file: str
    test_method: str
    error_type: str
    error_message: str
    stack_trace: str
    line_number: Optional[int] = None


@dataclass
class CodeFixSuggestion:
    """コード修正提案を表すデータクラス"""
    id: str
    type: str
    priority: str
    description: str
    current_code: str
    suggested_code: str
    safety_score: float
    impact_analysis: Dict[str, Any] = None
    auto_applicable: bool = True
    line_number: Optional[int] = None

    def __post_init__(self):
        if self.impact_analysis is None:
            self.impact_analysis = {}


@dataclass
class TDDGoal:
    """TDD目標を表すデータクラス"""
    description: str
    acceptance_criteria: List[str]
    priority: str
    estimated_effort: str
    # TODO: Implement Logic: 本モジュールはロジックを持たず、型定義のみを提供する。
