"""Small approval-state operations shared by TaskManager approval paths."""

from __future__ import annotations

import time
from typing import Any


class ApprovalWorkflow:
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    def response_value(
        self,
        intent: str,
        entities: dict,
        agree_intent: str,
        disagree_intent: str,
        approved_value: str,
        rejected_value: str,
    ) -> Any:
        if intent == agree_intent:
            return approved_value
        if intent == disagree_intent:
            return rejected_value
        response = entities.get("user_response")
        if isinstance(response, dict):
            return response.get("value", intent)
        return intent

    def record_decision(self, task: dict, action: str) -> None:
        history = task.setdefault("approval_history", [])
        history.append({
            "timestamp": time.time(),
            "action": action,
            "task_type": task.get("type", "SIMPLE_TASK"),
            "task_name": task.get("name"),
        })
