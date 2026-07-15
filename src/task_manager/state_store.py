"""TaskManager-facing state store boundary.

TaskManager owns task transitions; this adapter owns whether and how state is
persisted.  Keeping the optional behavior here avoids persistence branching
through the task transition logic.
"""

from __future__ import annotations

from typing import Any


class TaskStateStore:
    def __init__(
        self,
        enabled: bool,
        storage_dir: str,
        max_age_hours: int,
        log_manager=None,
    ):
        self.enabled = enabled
        self._persistence = None
        if enabled:
            from .task_persistence import TaskPersistence

            self._persistence = TaskPersistence(
                storage_dir=storage_dir,
                max_age_hours=max_age_hours,
                log_manager=log_manager,
            )

    def save_task_state(self, session_id: str, task_state: dict) -> bool:
        if not self._persistence:
            return False
        return self._persistence.save_task_state(session_id, task_state)

    def load_task_state(self, session_id: str) -> dict | None:
        if not self._persistence:
            return None
        return self._persistence.load_task_state(session_id)

    def delete_task_state(self, session_id: str) -> bool:
        if not self._persistence:
            return False
        return self._persistence.delete_task_state(session_id)

    def cleanup_old_states(self) -> None:
        if self._persistence:
            self._persistence.cleanup_old_states()
