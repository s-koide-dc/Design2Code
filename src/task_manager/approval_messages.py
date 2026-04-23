# -*- coding: utf-8 -*-
# src/task_manager/approval_messages.py

"""
承認メッセージのテンプレート管理
"""

import json
import os
from typing import Dict, Any

class ApprovalMessageGenerator:
    """承認メッセージの生成を管理するクラス"""
    
    def __init__(self, task_definitions_path: str = "resources/task_definitions.json"):
        self.task_definitions = self._load_task_definitions(task_definitions_path)
        self.templates = {
            "COMPOUND_TASK_OVERALL": {
                "default": "複合タスク「{task_name}」を開始します。このタスクは複数のステップを含みます。実行してよろしいですか？"
            },
            "CRITICAL_SUBTASK": {
                "FILE_DELETE": "危険なアクション：ファイル '{filename}' を削除します。この操作は元に戻せません。実行してよろしいですか？",
                "CMD_RUN": "危険なアクション：コマンド '{command}' を実行します。システムに影響を与える可能性があります。実行してよろしいですか？",
                "default": "危険なアクション「{subtask_name}」を実行します。複合タスク「{task_name}」の一部として実行されます。よろしいですか？"
            }
        }

    def _load_task_definitions(self, filepath: str) -> dict:
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    
    def generate_overall_approval_message(self, task_name: str, parameters: Dict[str, Any], task_definitions: Dict[str, Any] = None) -> str:
        """複合タスク全体承認メッセージを生成"""
        # 1. Try provided task definitions, then fallback to self.task_definitions
        definitions = task_definitions if task_definitions is not None else self.task_definitions
        
        task_def = definitions.get(task_name, {})
        overall_template = task_def.get("templates", {}).get("overall_approval")
        
        if not overall_template:
            # Fallback to hardcoded templates
            overall_template = self.templates["COMPOUND_TASK_OVERALL"].get(
                task_name, 
                self.templates["COMPOUND_TASK_OVERALL"]["default"]
            )
        
        try:
            # パラメータから値を抽出
            format_params = {}
            for key, value in parameters.items():
                if isinstance(value, dict) and "value" in value:
                    format_params[key] = value["value"]
                else:
                    format_params[key] = str(value)
            
            format_params["task_name"] = task_name
            return overall_template.format(**format_params)
        except (KeyError, ValueError):
            # フォーマットエラーの場合はデフォルトメッセージ
            default_tpl = self.templates["COMPOUND_TASK_OVERALL"].get("default")
            return default_tpl.format(task_name=task_name)
    
    def generate_critical_subtask_message(self, task_name: str, subtask_name: str, parameters: Dict[str, Any], task_definitions: Dict[str, Any] = None) -> str:
        """クリティカルサブタスク承認メッセージを生成"""
        definitions = task_definitions if task_definitions is not None else self.task_definitions
        # 1. Try to get template from subtask's own definition first
        subtask_def = definitions.get(subtask_name, {})
        template = subtask_def.get("templates", {}).get("step_approval")
        
        if not template:
            template = self.templates["CRITICAL_SUBTASK"].get(
                subtask_name,
                self.templates["CRITICAL_SUBTASK"]["default"]
            )
        
        try:
            # パラメータから値を抽出
            format_params = {}
            for key, value in parameters.items():
                if isinstance(value, dict) and "value" in value:
                    format_params[key] = value["value"]
                else:
                    format_params[key] = str(value)
            
            format_params["task_name"] = task_name
            format_params["subtask_name"] = subtask_name
            return template.format(**format_params)
        except (KeyError, ValueError):
            # フォーマットエラーの場合はデフォルトメッセージ
            return self.templates["CRITICAL_SUBTASK"]["default"].format(
                task_name=task_name, 
                subtask_name=subtask_name
            )