# -*- coding: utf-8 -*-
# src/autonomous_learning/pattern_learner.py

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
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
    safety_evidence: Dict[str, Any] = field(default_factory=dict)

class PatternLearner:
    """パターン学習を担当するクラス"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.validation_diagnostics: List[Dict[str, Any]] = []

    def learn_from_patterns(self, patterns: Dict[str, List[LearningPattern]]) -> List[RuleSuggestion]:
        """パターンから新しいルールを学習"""
        self.validation_diagnostics = []
        suggestions = []
        expected_rule_types = {
            "success": "intent_rule",
            "error": "retry_rule",
            "improvement": "clarification_rule",
            "clarification_fix": "intent_rule",
        }
        for category, expected_rule_type in expected_rule_types.items():
            for pattern in patterns.get(category, []):
                suggestion = self._create_structured_suggestion(
                    pattern,
                    expected_rule_type,
                )
                if suggestion:
                    suggestions.append(suggestion)
        return suggestions

    def _create_structured_suggestion(
        self,
        pattern: LearningPattern,
        expected_rule_type: str,
    ) -> Optional[RuleSuggestion]:
        proposal = pattern.context.get("proposed_rule")
        if not isinstance(proposal, dict):
            self._record_invalid(pattern, "proposed_rule_missing")
            return None

        rule_type = proposal.get("rule_type")
        rule_definition = proposal.get("rule_definition")
        impact_scope = proposal.get("impact_scope")
        risk_level = proposal.get("risk_level")
        explanation = proposal.get("explanation")
        if rule_type != expected_rule_type:
            self._record_invalid(pattern, "rule_type_mismatch")
            return None
        if not isinstance(rule_definition, dict) or not rule_definition:
            self._record_invalid(pattern, "rule_definition_invalid")
            return None
        if not isinstance(impact_scope, str) or not impact_scope:
            self._record_invalid(pattern, "impact_scope_invalid")
            return None
        if risk_level not in {"low", "medium", "high"}:
            self._record_invalid(pattern, "risk_level_invalid")
            return None
        if not isinstance(explanation, str) or not explanation:
            self._record_invalid(pattern, "explanation_invalid")
            return None

        supporting_evidence = proposal.get("supporting_evidence", [])
        if not isinstance(supporting_evidence, list) or any(
            not isinstance(item, dict) for item in supporting_evidence
        ):
            self._record_invalid(pattern, "supporting_evidence_invalid")
            return None
        safety_evidence = proposal.get("safety_evidence")
        if not isinstance(safety_evidence, dict):
            self._record_invalid(pattern, "safety_evidence_invalid")
            return None

        return RuleSuggestion(
            rule_type=rule_type,
            rule_definition=dict(rule_definition),
            confidence=1.0,
            impact_scope=impact_scope,
            risk_level=risk_level,
            explanation=explanation,
            supporting_evidence=list(supporting_evidence),
            safety_evidence=dict(safety_evidence),
        )

    def _record_invalid(
        self,
        pattern: LearningPattern,
        reason: str,
    ) -> None:
        self.validation_diagnostics.append({
            "type": "INVALID_RULE_PROPOSAL",
            "reason": reason,
            "evidence_type": pattern.context.get("evidence_type"),
            "pattern": pattern.pattern,
        })
