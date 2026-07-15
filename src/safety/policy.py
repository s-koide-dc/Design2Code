"""Single source of truth for command and action safety policy defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass
class SafetyPolicy:
    destructive_intents: set[str] = field(default_factory=lambda: {
        "FILE_DELETE", "FILE_MOVE", "BACKUP_AND_DELETE", "APPLY_CODE_FIX",
        "APPLY_REFACTORING", "FILE_APPEND", "CMD_RUN",
    })
    cautionary_intents: set[str] = field(default_factory=lambda: {"FILE_CREATE"})
    safe_commands: list[str] = field(default_factory=lambda: [
        "git", "ls", "dir", "type", "cat", "echo", "date", "time",
        "dotnet", "npm", "py", "python",
    ])
    simple_whitelist: list[str] = field(default_factory=lambda: [
        "dir", "ls", "echo", "type", "cat", "date", "time",
    ])
    allowed_subcommands: dict[str, list[str]] = field(default_factory=lambda: {
        "git": ["status", "log", "diff", "show", "branch", "rev-parse", "ls-files"],
        "dotnet": ["test", "build", "restore", "clean", "list"],
        "npm": ["test", "list"],
    })
    disallowed_args: dict[str, list[str]] = field(default_factory=lambda: {
        "python": ["-c", "-m"], "py": ["-c", "-m"],
    })
    python_allowed_dirs: list[str] = field(default_factory=lambda: ["scripts"])
    python_allowed_scripts: list[str] = field(default_factory=list)
    blocked_metacharacters: list[str] = field(default_factory=lambda: ["&", "|", ";", ">", "<", chr(96), "$"])
    read_commands: list[str] = field(default_factory=lambda: ["cat", "type"])
    list_commands: list[str] = field(default_factory=lambda: ["ls", "dir"])
    read_allowed_dirs: list[str] = field(default_factory=lambda: ["AIFiles", "config", "docs", "scripts", "src", "tests"])
    read_blocked_rules: list[dict[str, str]] = field(default_factory=lambda: [
        {"pattern": ".env", "match": "basename_exact"},
        {"pattern": "private_key", "match": "segment"},
        {"pattern": "api_key", "match": "segment"},
        {"pattern": "apikey", "match": "segment"},
        {"pattern": "secrets", "match": "segment"},
        {"pattern": "secret", "match": "segment"},
        {"pattern": "token", "match": "segment"},
    ])

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any] | None) -> "SafetyPolicy":
        defaults = cls()
        values: dict[str, Any] = {}
        mapping = mapping or {}
        for name in defaults.__dataclass_fields__:
            value = mapping.get(name, getattr(defaults, name))
            if name in {"destructive_intents", "cautionary_intents"}:
                value = set(value or [])
            elif name in {"allowed_subcommands", "disallowed_args"}:
                value = {str(key): list(items or []) for key, items in (value or {}).items()}
            elif name == "read_blocked_rules":
                value = [dict(item) for item in (value or [])]
            else:
                value = list(value or [])
            values[name] = value
        return cls(**values)
