"""Command validation shared by planning and execution boundaries."""

from __future__ import annotations

import shlex
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandValidation:
    parts: list[str] | None = None
    error_message: str | None = None

    @property
    def ok(self) -> bool:
        return self.error_message is None


class CommandPolicyValidator:
    def __init__(self, executor):
        self.executor = executor

    def validate(self, command: str) -> CommandValidation:
        try:
            parts = shlex.split(command)
        except ValueError:
            return CommandValidation(error_message="コマンドの形式が正しくありません。")
        if not parts:
            return CommandValidation(error_message="コマンドが空です。")

        base_cmd = parts[0].lower()
        if base_cmd not in self.executor.safe_commands:
            return CommandValidation(error_message=f"コマンド '{base_cmd}' は許可されていません。")

        allowed = self.executor.allowed_subcommands.get(base_cmd, [])
        if allowed and (len(parts) < 2 or parts[1].lower() not in allowed):
            allowed_str = ", ".join(allowed)
            return CommandValidation(
                error_message=f"コマンド '{base_cmd}' のサブコマンドが許可されていないか、指定されていません。許可されているサブコマンド: {allowed_str}"
            )

        disallowed = [arg.lower() for arg in self.executor.disallowed_args.get(base_cmd, [])]
        if any(part.lower() in disallowed for part in parts[1:]):
            return CommandValidation(error_message="コマンド引数に禁止されたオプションが含まれています。")

        if any(
            char in part
            for part in parts[1:]
            for char in self.executor.blocked_metacharacters
        ):
            return CommandValidation(error_message="コマンド引数に不正な文字が含まれています。")

        if base_cmd in self.executor.read_commands:
            error = self._validate_paths(parts, "読み取り")
            if error:
                return CommandValidation(error_message=error)

        if base_cmd in self.executor.list_commands:
            error = self._validate_paths(parts, "一覧取得", require_target=False)
            if error:
                return CommandValidation(error_message=error)

        if base_cmd in {"python", "py"}:
            script_path = self.executor._extract_python_script_path(parts)
            if not script_path:
                return CommandValidation(error_message="python/py はスクリプトファイルの指定が必須です。")
            if not self.executor._is_allowed_python_script(script_path):
                return CommandValidation(error_message="python/py の実行は scripts 配下のスクリプトに限定されています。")
            if self.executor.python_allowed_scripts and not self.executor._is_whitelisted_python_script(script_path):
                return CommandValidation(error_message="python/py の実行は許可されたスクリプトに限定されています。")

        return CommandValidation(parts=parts)

    def _validate_paths(self, parts: list[str], operation: str, require_target: bool = True) -> str | None:
        targets = self.executor._extract_non_option_args(parts)
        if require_target and not targets:
            return f"{operation}対象のパスが指定されていません。"
        for target in targets:
            if not self.executor._is_allowed_read_path(target):
                return f"{operation}対象のパスが許可範囲外です。"
            if self.executor._is_blocked_read_path(target):
                return f"{operation}対象のパスが禁止されています。"
        return None
