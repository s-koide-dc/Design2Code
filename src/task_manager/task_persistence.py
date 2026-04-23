# -*- coding: utf-8 -*-
# src/task_manager/task_persistence.py

"""
タスク状態の永続化機能
プロセス再起動時の状態復旧をサポート
"""

import json
import os
import time
from typing import Dict, Optional
from datetime import datetime, timedelta

class TaskPersistence:
    """タスク状態の永続化を管理するクラス"""
    
    def __init__(self, storage_dir: str = "data/task_states", max_age_hours: int = 24, log_manager=None):
        """
        Args:
            storage_dir: 状態ファイルの保存ディレクトリ
            max_age_hours: 状態ファイルの最大保持時間（時間）
            log_manager: LogManagerインスタンス
        """
        self.storage_dir = storage_dir
        self.max_age_hours = max_age_hours
        self.log_manager = log_manager
        self._ensure_storage_dir()
    
    def _ensure_storage_dir(self):
        """ストレージディレクトリの存在を確認・作成"""
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)
    
    def _get_state_file_path(self, session_id: str) -> str:
        """セッションIDに対応する状態ファイルのパスを取得"""
        safe_session_id = "".join(c for c in session_id if c.isalnum() or c in "-_")
        return os.path.join(self.storage_dir, f"task_state_{safe_session_id}.json")
    
    def _log_error(self, message: str):
        """エラーログの出力"""
        if self.log_manager:
            self.log_manager.log_event("task_persistence_error", {"message": message}, level="ERROR")
    
    def save_task_state(self, session_id: str, task_state: dict) -> bool:
        """
        タスク状態を保存
        
        Args:
            session_id: セッションID
            task_state: 保存するタスク状態
            
        Returns:
            bool: 保存成功の可否
        """
        try:
            state_data = {
                "session_id": session_id,
                "task_state": task_state,
                "timestamp": datetime.now().isoformat(),
                "version": "1.0"
            }
            
            file_path = self._get_state_file_path(session_id)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            self._log_error(f"Error saving task state for session {session_id}: {e}")
            return False
    
    def load_task_state(self, session_id: str) -> Optional[dict]:
        """
        タスク状態を読み込み
        
        Args:
            session_id: セッションID
            
        Returns:
            Optional[dict]: 読み込まれたタスク状態（存在しない場合はNone）
        """
        try:
            file_path = self._get_state_file_path(session_id)
            
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # 古すぎる状態は無視
            timestamp = datetime.fromisoformat(state_data.get("timestamp", ""))
            if datetime.now() - timestamp > timedelta(hours=self.max_age_hours):
                self.delete_task_state(session_id)
                return None
            
            return state_data.get("task_state")
        
        except Exception as e:
            self._log_error(f"Error loading task state for session {session_id}: {e}")
            return None
    
    def delete_task_state(self, session_id: str) -> bool:
        """
        タスク状態を削除
        
        Args:
            session_id: セッションID
            
        Returns:
            bool: 削除成功の可否
        """
        try:
            file_path = self._get_state_file_path(session_id)
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except Exception as e:
            self._log_error(f"Error deleting task state for session {session_id}: {e}")
            return False
    
    def cleanup_old_states(self):
        """古い状態ファイルをクリーンアップ"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.max_age_hours)
            
            for filename in os.listdir(self.storage_dir):
                if not filename.startswith("task_state_"):
                    continue
                
                file_path = os.path.join(self.storage_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        state_data = json.load(f)
                    
                    timestamp = datetime.fromisoformat(state_data.get("timestamp", ""))
                    if timestamp < cutoff_time:
                        os.remove(file_path)
                        
                except Exception:
                    # 読み込めないファイルは削除
                    os.remove(file_path)
                    
        except Exception as e:
            self._log_error(f"Error during cleanup: {e}")