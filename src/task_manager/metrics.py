# -*- coding: utf-8 -*-
# src/task_manager/metrics.py

"""
TaskManagerのパフォーマンス監視とメトリクス収集
"""

import time
from collections import defaultdict, deque
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class TaskMetrics:
    """タスクのメトリクス情報"""
    task_name: str
    session_id: str
    start_time: float
    end_time: Optional[float] = None
    state_transitions: List[str] = None
    approval_requests: int = 0
    interruptions: int = 0
    final_state: Optional[str] = None
    
    def __post_init__(self):
        if self.state_transitions is None:
            self.state_transitions = []
    
    @property
    def duration(self) -> Optional[float]:
        """タスクの実行時間（秒）"""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def is_completed(self) -> bool:
        """タスクが完了しているか"""
        return self.final_state in ["COMPLETED", "FAILED", "CANCELLED"]

class TaskManagerMetrics:
    """TaskManagerのメトリクス収集・分析クラス"""
    
    def __init__(self, max_history_size: int = 1000):
        self.max_history_size = max_history_size
        self.active_tasks: Dict[str, TaskMetrics] = {}  # session_id -> metrics
        self.completed_tasks: deque = deque(maxlen=max_history_size)
        self.counters = defaultdict(int)
        self.timing_stats = defaultdict(list)
    
    def start_task(self, session_id: str, task_name: str, task_type: str = "SIMPLE_TASK"):
        """タスク開始の記録"""
        metrics = TaskMetrics(
            task_name=task_name,
            session_id=session_id,
            start_time=time.time()
        )
        self.active_tasks[session_id] = metrics
        self.counters[f"tasks_started_{task_type}"] += 1
        self.counters["tasks_started_total"] += 1
    
    def record_state_transition(self, session_id: str, from_state: str, to_state: str):
        """状態遷移の記録"""
        if session_id in self.active_tasks:
            metrics = self.active_tasks[session_id]
            transition = f"{from_state} -> {to_state}"
            metrics.state_transitions.append(transition)
            self.counters[f"transitions_{transition}"] += 1
    
    def record_approval_request(self, session_id: str, approval_type: str):
        """承認要求の記録"""
        if session_id in self.active_tasks:
            self.active_tasks[session_id].approval_requests += 1
            self.counters[f"approvals_{approval_type}"] += 1
            self.counters["approvals_total"] += 1
    
    def record_interruption(self, session_id: str, interruption_type: str):
        """割り込みの記録"""
        if session_id in self.active_tasks:
            self.active_tasks[session_id].interruptions += 1
            self.counters[f"interruptions_{interruption_type}"] += 1
            self.counters["interruptions_total"] += 1
    
    def complete_task(self, session_id: str, final_state: str):
        """タスク完了の記録"""
        if session_id in self.active_tasks:
            metrics = self.active_tasks[session_id]
            metrics.end_time = time.time()
            metrics.final_state = final_state
            
            # 統計情報の更新
            if metrics.duration:
                self.timing_stats[metrics.task_name].append(metrics.duration)
                self.timing_stats["all_tasks"].append(metrics.duration)
            
            self.counters[f"tasks_completed_{final_state}"] += 1
            self.counters["tasks_completed_total"] += 1
            
            # 完了タスクリストに移動
            self.completed_tasks.append(metrics)
            del self.active_tasks[session_id]
    
    def get_summary_stats(self) -> Dict:
        """サマリー統計の取得"""
        stats = {
            "active_tasks_count": len(self.active_tasks),
            "completed_tasks_count": len(self.completed_tasks),
            "counters": dict(self.counters)
        }
        
        # 実行時間統計
        timing_summary = {}
        for task_name, durations in self.timing_stats.items():
            if durations:
                timing_summary[task_name] = {
                    "count": len(durations),
                    "avg_duration": sum(durations) / len(durations),
                    "min_duration": min(durations),
                    "max_duration": max(durations)
                }
        stats["timing_stats"] = timing_summary
        
        return stats
    
    def get_active_tasks_info(self) -> List[Dict]:
        """アクティブタスクの情報取得"""
        return [
            {
                "session_id": metrics.session_id,
                "task_name": metrics.task_name,
                "duration_so_far": time.time() - metrics.start_time,
                "state_transitions_count": len(metrics.state_transitions),
                "approval_requests": metrics.approval_requests,
                "interruptions": metrics.interruptions
            }
            for metrics in self.active_tasks.values()
        ]
    
    def cleanup_stale_tasks(self, max_age_hours: int = 24):
        """古いアクティブタスクのクリーンアップ"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        stale_sessions = [
            session_id for session_id, metrics in self.active_tasks.items()
            if metrics.start_time < cutoff_time
        ]
        
        for session_id in stale_sessions:
            self.complete_task(session_id, "TIMEOUT")
        
        return len(stale_sessions)
        # TODO: Implement Logic: **イベント記録**:
            # TODO: Implement Logic: **完了処理**:
                # TODO: Implement Logic: **クリーンアップ**:
                    # TODO: Implement Logic: 指定時間（例: 24時間）を経過したアクティブタスクを自動的にタイムアウトとして処理。
