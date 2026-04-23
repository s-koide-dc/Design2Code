# -*- coding: utf-8 -*-
# src/task_manager/session_manager.py

import time
import sys

class SessionManager:
    """セッションのライフサイクルと統計を管理するクラス"""
    
    def __init__(self, active_tasks: dict, session_last_activity: dict, config):
        self.active_tasks = active_tasks
        self.session_last_activity = session_last_activity
        self.config = config

    def update_activity(self, session_id: str):
        """セッションの最終活動時刻を更新"""
        self.session_last_activity[session_id] = time.time()

    def get_stats(self) -> dict:
        """セッション統計の取得"""
        return {
            "active_sessions": len(self.active_tasks),
            "max_sessions": self.config.max_active_sessions,
            "session_timeout_minutes": self.config.session_timeout_minutes
        }

    def get_session_id(self, context: dict) -> str:
        """contextからsession_idを抽出、またはデフォルトを返す"""
        text = context.get("original_text", "")
        sid = _extract_session_id(text)
        if sid:
            return sid
        return context.get("session_id", "default_session")

    def is_task_active(self, session_id: str) -> bool:
        """セッションにアクティブなタスクがあるかチェック"""
        return session_id in self.active_tasks

    def get_task_state(self, session_id: str) -> dict:
        """タスクの現在状態を取得"""
        task = self.active_tasks.get(session_id)
        if not task:
            return {"status": "no_active_task"}
        
        state_info = {
            "status": "active",
            "task_id": task.get("id"),
            "task_name": task.get("name"),
            "task_type": task.get("type", "SIMPLE_TASK"),
            "state": task.get("state"),
            "parameters": task.get("parameters", {}),
            "clarification_needed": task.get("clarification_needed", False)
        }
        
        if task.get("type") == "COMPOUND_TASK":
            state_info.update({
                "current_subtask_index": task.get("current_subtask_index", 0),
                "total_subtasks": len(task.get("subtasks", [])),
                "subtasks": task.get("subtasks", [])
            })
        
        return state_info

    def get_memory_usage_stats(self) -> dict:
        """メモリ使用量統計の取得"""
        stats = {
            "active_tasks_count": len(self.active_tasks),
            "session_activity_count": len(self.session_last_activity),
            "total_task_objects": sum(1 for task in self.active_tasks.values()),
        }
        
        # タスクごとのメモリ使用量推定
        total_task_size = 0
        for task in self.active_tasks.values():
            total_task_size += sys.getsizeof(str(task))
        
        stats["estimated_task_memory_bytes"] = total_task_size
        return stats

    def validate_integrity(self, session_id: str, task_definitions: dict) -> dict:
        """タスクの整合性チェック"""
        task = self.active_tasks.get(session_id)
        if not task:
            return {"valid": True, "message": "No active task"}
        
        issues = []
        
        # 基本的な必須フィールドのチェック
        required_fields = ["id", "name", "state", "parameters"]
        for field in required_fields:
            if field not in task:
                issues.append(f"Missing required field: {field}")
        
        # タスク定義の存在チェック
        task_def = task_definitions.get(task.get("name"))
        if not task_def:
            issues.append(f"Task definition not found: {task.get('name')}")
        
        # 複合タスクの整合性チェック
        if task.get("type") == "COMPOUND_TASK":
            subtasks = task.get("subtasks", [])
            current_index = task.get("current_subtask_index", 0)
            
            if current_index > len(subtasks):
                issues.append(f"Invalid subtask index: {current_index} > {len(subtasks)}")
            
            for i, subtask in enumerate(subtasks):
                if "name" not in subtask:
                    issues.append(f"Subtask {i} missing name")
                if "state" not in subtask:
                    issues.append(f"Subtask {i} missing state")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "task_id": task.get("id"),
            "task_name": task.get("name")
        }
        # TODO: Implement Logic: **ライフサイクル管理**: 最終活動時刻の更新と、アクティブなタスク状態の保持。
            # TODO: Implement Logic: **統計収集**:
                # TODO: Implement Logic: アクティブセッション数、メモリ使用量の推定値を取得。
                # TODO: Implement Logic: 必須フィールドの欠落や、定義されていないタスクの実行、不整合なサブタスクインデックスを検出。

def _extract_session_id(text: str) -> str | None:
    if not text:
        return None
    prefix = "session_id:"
    if not text.startswith(prefix):
        return None
    rest = text[len(prefix):].lstrip()
    if not rest:
        return None
    i = 0
    while i < len(rest) and not rest[i].isspace():
        i += 1
    return rest[:i] if i > 0 else None
