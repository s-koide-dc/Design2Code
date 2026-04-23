# -*- coding: utf-8 -*-
# src/context_manager/context_manager.py

class ContextManager:
    def __init__(self, max_history=10):
        """
        Initializes the Context Manager.
        
        Args:
            max_history (int): Maximum number of past contexts to retain.
        """
        self.history = {} # session_id -> list of history entries
        self.max_history = max_history
        self.pending_confirmation_plans = {} # session_id -> plan awaiting user confirmation
        self.awaiting_feedback = {} # session_id -> boolean

    def add_context(self, context: dict):
        """
        Adds a completed context to the history.
        """
        session_id = context.get("session_id", "default_session")
        if session_id not in self.history:
            self.history[session_id] = []

        # We store a shallow copy or specific parts to avoid massive memory bloat
        # In this prototype, we store essential analysis results
        entry = {
            "original_text": context.get("original_text"),
            "intent": context.get("analysis", {}).get("intent"),
            "topics": context.get("analysis", {}).get("topics", []),
            "entities": context.get("analysis", {}).get("entities", {}),
            "action_result": context.get("action_result", {})
        }
        
        history_list = self.history[session_id]
        history_list.append(entry)
        if len(history_list) > self.max_history:
            history_list.pop(0)

    def get_last_context(self, session_id="default_session"):
        """Returns the most recent history entry or None for a session."""
        history_list = self.history.get(session_id, [])
        return history_list[-1] if history_list else None

    def get_history(self, session_id="default_session"):
        """Returns the full history list for a session."""
        return self.history.get(session_id, [])

    def set_pending_confirmation_plan(self, plan: dict, session_id="default_session"):
        """Stores a plan that is awaiting user confirmation."""
        self.pending_confirmation_plans[session_id] = plan

    def get_pending_confirmation_plan(self, session_id="default_session") -> dict:
        """Retrieves the plan that is awaiting user confirmation."""
        return self.pending_confirmation_plans.get(session_id)

    def clear_pending_confirmation_plan(self, session_id="default_session"):
        """Clears the stored pending confirmation plan."""
        if session_id in self.pending_confirmation_plans:
            del self.pending_confirmation_plans[session_id]
            # TODO: Implement Logic: **履歴の整理（対話ターン制限）**:

    def set_awaiting_feedback(self, session_id: str, is_awaiting: bool):
        """Sets the feedback awaiting state for a session."""
        self.awaiting_feedback[session_id] = is_awaiting

    def is_awaiting_feedback(self, session_id: str) -> bool:
        """Checks if the session is awaiting feedback."""
        return self.awaiting_feedback.get(session_id, False)
