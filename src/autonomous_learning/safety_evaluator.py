# -*- coding: utf-8 -*-
# src/autonomous_learning/safety_evaluator.py

import logging
from typing import Dict, List, Any
from .pattern_learner import RuleSuggestion

class SafetyEvaluator:
    """安全性評価を担当するクラス"""
    
    def __init__(self, safety_config: Dict[str, Any]):
        self.safety_config = safety_config
        self.logger = logging.getLogger(__name__)
        self.evaluation_diagnostics: List[Dict[str, Any]] = []
    
    def evaluate_suggestions(self, suggestions: List[RuleSuggestion]) -> List[RuleSuggestion]:
        """ルール提案の安全性を評価"""
        self.evaluation_diagnostics = []
        evaluated_suggestions = []
        for suggestion in suggestions:
            rejection_reason = self._rejection_reason(suggestion)
            if rejection_reason is None:
                evaluated_suggestions.append(suggestion)
            else:
                self.evaluation_diagnostics.append({
                    "type": "SAFETY_EVIDENCE_REJECTED",
                    "reason": rejection_reason,
                    "rule_type": suggestion.rule_type,
                })
                self.logger.info("安全性制約により提案を却下: %s", suggestion.explanation)
        return evaluated_suggestions

    def _rejection_reason(
        self,
        suggestion: RuleSuggestion,
    ) -> str | None:
        allowed_risk_levels = self.safety_config.get(
            "allowed_risk_levels",
            ["low", "medium"],
        )
        if (
            not isinstance(allowed_risk_levels, list)
            or any(
                risk not in {"low", "medium", "high"}
                for risk in allowed_risk_levels
            )
        ):
            return "safety_configuration_invalid"
        if suggestion.risk_level not in allowed_risk_levels:
            return "risk_level_not_allowed"

        evidence = suggestion.safety_evidence
        if not isinstance(evidence, dict) or not evidence:
            return "safety_evidence_missing"
        if evidence.get("reviewed") is not True:
            return "safety_review_not_completed"
        if evidence.get("decision") != "approve":
            return "safety_review_not_approved"
        controls = evidence.get("controls")
        if not isinstance(controls, list) or not controls:
            return "safety_controls_missing"
        for control in controls:
            if not isinstance(control, dict):
                return "safety_control_invalid"
            if not isinstance(control.get("control_id"), str):
                return "safety_control_invalid"
            if control.get("passed") is not True:
                return "safety_control_failed"
        return None
