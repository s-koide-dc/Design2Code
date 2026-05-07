# -*- coding: utf-8 -*-
import os
import sys
from typing import Any


class _SafeStream:
    def __init__(self, stream):
        self._stream = stream
        self._stdout_guard = True

    def write(self, data: Any) -> int:
        try:
            return self._stream.write(data)
        except Exception:
            return 0

    def flush(self) -> None:
        try:
            self._stream.flush()
        except Exception:
            pass

    def isatty(self) -> bool:
        try:
            return bool(self._stream.isatty())
        except Exception:
            return False

    def __getattr__(self, name: str):
        return getattr(self._stream, name)


def install_stdout_guard() -> None:
    if not hasattr(sys, "stdout") or not hasattr(sys, "stderr"):
        return
    if not getattr(sys.stdout, "_stdout_guard", False):
        sys.stdout = _SafeStream(sys.stdout)
    if not getattr(sys.stderr, "_stdout_guard", False):
        sys.stderr = _SafeStream(sys.stderr)


def is_debug_stdout_enabled() -> bool:
    flag = str(os.environ.get("NLP_DEBUG_STDOUT", "")).strip().lower()
    return flag in {"1", "true", "yes", "on"}


def debug_print(message: Any) -> None:
    if not is_debug_stdout_enabled():
        return
    try:
        print(message)
    except OSError:
        pass
