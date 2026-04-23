# -*- coding: utf-8 -*-
# src/autonomous_learning/pattern_learner.py

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from .log_analyzer import LearningPattern

@dataclass
class RuleSuggestion:
    """ルール提案を表すデータクラス"""
    rule_type: str  # 'intent_rule', 'retry_rule', 'clarification_rule'
    rule_definition: Dict[str, Any]
    confidence: float
    impact_scope: str
    risk_level: str  # 'low', 'medium', 'high'
    explanation: str
    supporting_evidence: List[Dict[str, Any]]

class PatternLearner:
    """パターン学習を担当するクラス"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def learn_from_patterns(self, patterns: Dict[str, List[LearningPattern]]) -> List[RuleSuggestion]:
        """パターンから新しいルールを学習"""
        suggestions = []
        for pattern in patterns['success']:
            if pattern.context.get('type') == 'intent_detection':
                suggestion = self._create_intent_rule_suggestion(pattern)
                if suggestion: suggestions.append(suggestion)
        
        for pattern in patterns['error']:
            suggestion = self._create_retry_rule_suggestion(pattern)
            if suggestion: suggestions.append(suggestion)
        
        for pattern in patterns['improvement']:
            suggestion = self._create_clarification_rule_suggestion(pattern)
            if suggestion: suggestions.append(suggestion)

        for pattern in patterns.get('clarification_fix', []):
            suggestion = self._create_intent_rule_suggestion(pattern)
            if suggestion: suggestions.append(suggestion)
        return suggestions
    
    def _check_rule_conflicts(self, rule_definition: Dict[str, Any]) -> bool:
        """既存ルールとの競合をチェック"""
        if not rule_definition: return True
        return False

    def _create_intent_rule_suggestion(self, pattern: LearningPattern) -> Optional[RuleSuggestion]:
        """意図検出ルールの提案を作成"""
        intent = pattern.context.get('intent')
        if not intent or pattern.confidence < 0.7: return None
        
        rule_definition = {
            'type': 'intent_detection',
            'pattern': pattern.pattern,
            'intent': intent,
            'confidence_boost': 0.2,
            'priority': 'normal'
        }
        
        if self._check_rule_conflicts(rule_definition): return None
        
        return RuleSuggestion(
            rule_type='intent_rule',
            rule_definition=rule_definition,
            confidence=pattern.confidence,
            impact_scope='intent_detection',
            risk_level='low',
            explanation=f"「{intent}」意図の検出精度向上のため、パターン「{pattern.pattern}」を追加",
            supporting_evidence=[{'frequency': pattern.frequency, 'examples': len(pattern.examples)}]
        )
    
    def _create_retry_rule_suggestion(self, pattern: LearningPattern) -> Optional[RuleSuggestion]:
        """リトライルールの提案を作成"""
        error_type = pattern.context.get('error_type')
        if not error_type or pattern.frequency < 2: return None
        
        rule_definition = {
            'type': 'retry_strategy',
            'error_pattern': error_type,
            'max_retries': 2,
            'backoff_strategy': 'exponential',
            'conditions': ['same_error_type']
        }
        
        if self._check_rule_conflicts(rule_definition): return None

        return RuleSuggestion(
            rule_type='retry_rule',
            rule_definition=rule_definition,
            confidence=0.8,
            impact_scope='error_handling',
            risk_level='medium',
            explanation=f"「{error_type}」エラーの自動回復のため、リトライ戦略を追加",
            supporting_evidence=[{'error_frequency': pattern.frequency, 'error_type': error_type}]
        )
    
    def _create_clarification_rule_suggestion(self, pattern: LearningPattern) -> Optional[RuleSuggestion]:
        """明確化ルールの提案を作成"""
        issue = pattern.context.get('issue')
        if not issue: return None
        
        if issue == 'low_intent_confidence':
            rule_definition = {
                'type': 'clarification_trigger',
                'condition': 'intent_confidence < 0.6',
                'message_template': 'より具体的に教えていただけますか？',
                'context_hints': True
            }
            explanation = "意図検出の信頼度が低い場合の明確化メッセージを改善"
        elif issue == 'frequent_clarification':
            rule_definition = {
                'type': 'clarification_optimization',
                'reduce_threshold': 0.1,
                'smart_suggestions': True,
                'context_aware': True
            }
            explanation = "頻繁な明確化要求を減らすため、より賢い明確化戦略を導入"
        else:
            return None
        
        if self._check_rule_conflicts(rule_definition): return None

        return RuleSuggestion(
            rule_type='clarification_rule',
            rule_definition=rule_definition,
            confidence=pattern.confidence,
            impact_scope='user_experience',
            risk_level='low',
            explanation=explanation,
            supporting_evidence=[{'frequency': pattern.frequency, 'issue': issue}]
        )
