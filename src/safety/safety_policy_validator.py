# -*- coding: utf-8 -*-
# src/safety/safety_policy_validator.py

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Optional
import json
import os
import shlex
from src.utils.context_utils import normalize_path

class RiskLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class SafetyCheckStatus(Enum):
    OK = "OK"
    BLOCK = "BLOCK"
    WARN = "WARN"

@dataclass
class SafetyCheckResult:
    status: SafetyCheckStatus
    message: str
    risk_level: RiskLevel

class SafetyPolicyValidator:
    """
    Planner段階でのアクションのリスク評価を行うバリデータ。
    ActionExecutorの実行時ブロックとは異なり、承認フローの制御や早期エラー通知を目的とする。
    """

    def __init__(self, action_executor, config_manager=None):
        """
        Args:
            action_executor: ActionExecutor instance to access safe_commands.
            config_manager: ConfigManager instance for safety policy.
        """
        self.action_executor = action_executor
        self.config_manager = config_manager
        
        # Load from config if available
        if config_manager:
            policy = config_manager.get_safety_policy()
            self.destructive_intents = set(policy.get("destructive_intents", []))
            self.cautionary_intents = set(policy.get("cautionary_intents", []))
            self.blocked_metacharacters = policy.get("blocked_metacharacters", ['&', '|', ';', '>', '<', '`', '$'])
            self.disallowed_args = policy.get("disallowed_args", {})
            self.allowed_subcommands = policy.get("allowed_subcommands", {})
            self.python_allowed_dirs = policy.get("python_allowed_dirs", ["scripts"])
            self.python_allowed_scripts = policy.get("python_allowed_scripts", [])
            self.read_commands = policy.get("read_commands", ["cat", "type"])
            self.list_commands = policy.get("list_commands", ["ls", "dir"])
            self.read_allowed_dirs = policy.get("read_allowed_dirs", [])
            self.read_blocked_rules = policy.get("read_blocked_rules", [])
        else:
            # Default values in case file loading fails
            self.destructive_intents = {
                "FILE_DELETE", "FILE_MOVE", "BACKUP_AND_DELETE",
                "APPLY_CODE_FIX", "APPLY_REFACTORING", "FILE_APPEND", "CMD_RUN"
            }
            self.cautionary_intents = {"FILE_CREATE"}
            self.blocked_metacharacters = ['&', '|', ';', '>', '<', '`', '$']
            self.disallowed_args = {}
            self.allowed_subcommands = {}
            self.python_allowed_dirs = ["scripts"]
            self.python_allowed_scripts = []
            self.read_commands = ["cat", "type"]
            self.list_commands = ["ls", "dir"]
            self.read_allowed_dirs = []
            self.read_blocked_rules = []

    def validate_action(self, action_method: str, parameters: Dict[str, Any], intent: str = None) -> SafetyCheckResult:
        """
        アクションのリスクを評価する。

        Args:
            action_method: The method name in ActionExecutor (e.g., '_run_command').
            parameters: The parameters for the action.
            intent: The original intent name (e.g., 'CMD_RUN').

        Returns:
            SafetyCheckResult
        """
        
        # 0. アクションメソッドの存在確認はPlannerでするが、念のため
        if not action_method:
             return SafetyCheckResult(SafetyCheckStatus.BLOCK, "アクションメソッドが未指定です。", RiskLevel.HIGH)

        # 1. ActionExecutorのホワイトリストと単純な整合性チェック
        # ActionExecutorのsafe_commandsにあるコマンドかどうかをCMD_RUNの場合にチェック
        if intent == "CMD_RUN":
            command_str = parameters.get("command", "")
            if not command_str:
                return SafetyCheckResult(SafetyCheckStatus.BLOCK, "コマンドが空です。", RiskLevel.HIGH)
            
            # コマンド名と引数を安全に分割
            try:
                cmd_parts = shlex.split(command_str)
            except ValueError:
                return SafetyCheckResult(SafetyCheckStatus.BLOCK, "コマンドの形式が正しくありません。", RiskLevel.HIGH)

            if not cmd_parts:
                return SafetyCheckResult(SafetyCheckStatus.BLOCK, "コマンドが空です。", RiskLevel.HIGH)

            cmd_name = cmd_parts[0]
            
            # メタ文字のチェック（インジェクション対策）
            # 許可されたコマンドであっても、&& や | などのチェーンが含まれる場合はリスクを高める
            if any(char in command_str for char in self.blocked_metacharacters):
                return SafetyCheckResult(
                    SafetyCheckStatus.BLOCK,
                    "コマンドに不正な文字（メタ文字）が含まれています。",
                    RiskLevel.HIGH
                )

            # 禁止オプションのチェック
            disallowed = [a.lower() for a in self.disallowed_args.get(cmd_name.lower(), [])]
            if disallowed:
                for part in cmd_parts[1:]:
                    if part.lower() in disallowed:
                        return SafetyCheckResult(
                            SafetyCheckStatus.BLOCK,
                            "コマンド引数に禁止されたオプションが含まれています。",
                            RiskLevel.HIGH
                        )

            # サブコマンド検証（Executorと一致）
            allowed = self.allowed_subcommands.get(cmd_name.lower(), [])
            if allowed:
                if len(cmd_parts) < 2 or cmd_parts[1].lower() not in [a.lower() for a in allowed]:
                    allowed_str = ", ".join(allowed)
                    return SafetyCheckResult(
                        SafetyCheckStatus.BLOCK,
                        f"コマンド '{cmd_name}' のサブコマンドが許可されていないか、指定されていません。許可されているサブコマンド: {allowed_str}",
                        RiskLevel.HIGH
                    )

            # python/py は scripts 配下のみ許可
            if cmd_name.lower() in ["python", "py"]:
                script_path = self._extract_python_script_path(cmd_parts)
                if not script_path:
                    return SafetyCheckResult(
                        SafetyCheckStatus.BLOCK,
                        "python/py はスクリプトファイルの指定が必須です。",
                        RiskLevel.HIGH
                    )
                if not self._is_allowed_python_script(script_path):
                    return SafetyCheckResult(
                        SafetyCheckStatus.BLOCK,
                        "python/py の実行は scripts 配下のスクリプトに限定されています。",
                        RiskLevel.HIGH
                    )
                if self.python_allowed_scripts and not self._is_whitelisted_python_script(script_path):
                    return SafetyCheckResult(
                        SafetyCheckStatus.BLOCK,
                        "python/py の実行は許可されたスクリプトに限定されています。",
                        RiskLevel.HIGH
                    )

            if cmd_name.lower() in self.read_commands:
                targets = self._extract_non_option_args(cmd_parts)
                if not targets:
                    return SafetyCheckResult(
                        SafetyCheckStatus.BLOCK,
                        "読み取り対象のパスが指定されていません。",
                        RiskLevel.HIGH
                    )
                for target in targets:
                    if not self._is_allowed_read_path(target):
                        return SafetyCheckResult(
                            SafetyCheckStatus.BLOCK,
                            "読み取り対象のパスが許可範囲外です。",
                            RiskLevel.HIGH
                        )
                    if self._is_blocked_read_path(target):
                        return SafetyCheckResult(
                            SafetyCheckStatus.BLOCK,
                            "読み取り対象のパスが禁止されています。",
                            RiskLevel.HIGH
                        )

            if cmd_name.lower() in self.list_commands:
                targets = self._extract_non_option_args(cmd_parts)
                for target in targets:
                    if not self._is_allowed_read_path(target):
                        return SafetyCheckResult(
                            SafetyCheckStatus.BLOCK,
                            "一覧取得対象のパスが許可範囲外です。",
                            RiskLevel.HIGH
                        )
                    if self._is_blocked_read_path(target):
                        return SafetyCheckResult(
                            SafetyCheckStatus.BLOCK,
                            "一覧取得対象のパスが禁止されています。",
                            RiskLevel.HIGH
                        )
            
            # ActionExecutorのリストを参照
            # Note: ActionExecutorの実装に依存するが、ここではsafe_commands属性があると仮定
            if hasattr(self.action_executor, "safe_commands"):
                safe_cmds = [c.lower() for c in self.action_executor.safe_commands]
                if cmd_name.lower() not in safe_cmds:
                    return SafetyCheckResult(
                        SafetyCheckStatus.BLOCK, 
                        f"コマンド '{cmd_name}' は許可されていません（ホワイトリスト外）。", 
                        RiskLevel.HIGH
                    )


        # 2. リスクレベルの判定
        risk_level = RiskLevel.LOW
        message = "Safety Check OK"
        status = SafetyCheckStatus.OK

        if intent in self.destructive_intents:
            risk_level = RiskLevel.HIGH
            message = "破壊的な変更または重要な操作が含まれています。"
        elif intent in self.cautionary_intents:
            risk_level = RiskLevel.MEDIUM
            message = "注意が必要な操作が含まれています。"
        elif intent == "BACKUP_AND_DELETE":
            risk_level = RiskLevel.HIGH
            message = "バックアップ付き削除が必要な操作です。"

        # 3. 特殊なパラメータチェック（将来的な拡張ポイント）
        # 例：重要なファイルへのアクセスなど
        
        return SafetyCheckResult(status, message, risk_level)

    def _extract_non_option_args(self, cmd_parts: list[str]) -> list[str]:
        args = []
        for part in cmd_parts[1:]:
            if part.startswith("-"):
                continue
            args.append(part)
        return args

    def _extract_python_script_path(self, cmd_parts: list[str]) -> str | None:
        for part in cmd_parts[1:]:
            if part.startswith("-"):
                continue
            return part
        return None

    def _is_allowed_python_script(self, script_path: str) -> bool:
        if not hasattr(self.action_executor, "workspace_root"):
            return False
        workspace_root = self.action_executor.workspace_root
        target = self.action_executor._safe_join(script_path)
        if not target or not os.path.exists(target):
            return False
        allowed_roots = []
        for rel in self.python_allowed_dirs:
            if not rel:
                continue
            allowed_roots.append(os.path.realpath(os.path.join(workspace_root, rel)))
        for root in allowed_roots:
            if target == root:
                continue
            if target.startswith(root + os.sep):
                return True
        return False

    def _is_whitelisted_python_script(self, script_path: str) -> bool:
        if not hasattr(self.action_executor, "workspace_root"):
            return False
        target = self.action_executor._safe_join(script_path)
        if not target:
            return False
        rel = os.path.relpath(target, self.action_executor.workspace_root)
        rel = normalize_path(rel)
        whitelist = [normalize_path(p) for p in self.python_allowed_scripts]
        return rel in whitelist

    def _is_allowed_read_path(self, path_text: str) -> bool:
        if not hasattr(self.action_executor, "workspace_root"):
            return False
        target = self.action_executor._safe_join(path_text)
        if not target:
            return False
        if not self.read_allowed_dirs:
            return True
        allowed_roots = []
        for rel in self.read_allowed_dirs:
            if not rel:
                continue
            allowed_roots.append(os.path.realpath(os.path.join(self.action_executor.workspace_root, rel)))
        for root in allowed_roots:
            if target == root:
                return True
            if target.startswith(root + os.sep):
                return True
        return False

    def _is_blocked_read_path(self, path_text: str) -> bool:
        if not hasattr(self.action_executor, "workspace_root"):
            return True
        if not self.read_blocked_rules:
            return False
        target = self.action_executor._safe_join(path_text)
        if not target:
            return True
        rel = normalize_path(os.path.relpath(target, self.action_executor.workspace_root)).lower()
        return self._matches_blocked_rules(rel, self.read_blocked_rules)

    def _matches_blocked_rules(self, rel_path: str, rules: list[dict]) -> bool:
        if not rel_path:
            return False
        segments = [seg for seg in rel_path.split("/") if seg]
        basename = segments[-1] if segments else ""
        base_no_ext = basename.rsplit(".", 1)[0] if "." in basename else basename
        tokens = self._split_tokens(base_no_ext)
        for rule in rules:
            pattern = str(rule.get("pattern", "")).lower()
            match = str(rule.get("match", "segment")).lower()
            if not pattern:
                continue
            if match == "basename_exact" and basename == pattern:
                return True
            if match == "segment":
                if pattern in tokens:
                    return True
        return False

    def _split_tokens(self, text: str) -> list[str]:
        tokens = []
        current = []
        for ch in str(text):
            if ch.isalnum():
                current.append(ch.lower())
            else:
                if current:
                    tokens.append("".join(current))
                    current = []
        if current:
            tokens.append("".join(current))
        return tokens
