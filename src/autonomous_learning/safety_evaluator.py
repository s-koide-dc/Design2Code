# -*- coding: utf-8 -*-
# src/autonomous_learning/safety_evaluator.py

import json
import logging
from typing import Dict, List, Any
from .pattern_learner import RuleSuggestion

class SafetyEvaluator:
    """安全性評価を担当するクラス"""
    
    def __init__(self, safety_config: Dict[str, Any]):
        self.safety_config = safety_config
        self.logger = logging.getLogger(__name__)
    
    def evaluate_suggestions(self, suggestions: List[RuleSuggestion]) -> List[RuleSuggestion]:
        """ルール提案の安全性を評価"""
        evaluated_suggestions = []
        for suggestion in suggestions:
            safety_score = self._calculate_safety_score(suggestion)
            suggestion.risk_level = self._determine_risk_level(safety_score)
            
            if self._passes_safety_constraints(suggestion):
                evaluated_suggestions.append(suggestion)
            else:
                self.logger.warning(f"安全性制約により提案を却下: {suggestion.explanation}")
        return evaluated_suggestions
    
    def _calculate_safety_score(self, suggestion: RuleSuggestion) -> float:
        """安全性スコアを計算"""
        score = 1.0
        if suggestion.rule_type == 'intent_rule':
            score *= 0.95
        elif suggestion.rule_type == 'retry_rule':
            score *= 0.7
        elif suggestion.rule_type == 'clarification_rule':
            score *= 0.98
        
        score *= suggestion.confidence
        
        if suggestion.impact_scope == 'system_wide':
            score *= 0.5
        elif suggestion.impact_scope == 'user_experience':
            score *= 0.9
        elif suggestion.impact_scope == 'intent_detection':
            score *= 0.95
        return max(0.0, min(1.0, score))
    
    def _determine_risk_level(self, safety_score: float) -> str:
        """安全性スコアからリスクレベルを決定"""
        if safety_score >= 0.8: return 'low'
        elif safety_score >= 0.6: return 'medium'
        else: return 'high'
    
    def _passes_safety_constraints(self, suggestion: RuleSuggestion) -> bool:
        """安全性制約をパスするかチェック"""
        if suggestion.risk_level == 'high': return False
        
        dangerous_keywords = self.safety_config.get('dangerous_keywords', [])
        rule_text = json.dumps(suggestion.rule_definition).lower()
        for keyword in dangerous_keywords:
            if keyword.lower() in rule_text: return False
        return True
