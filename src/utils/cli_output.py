# -*- coding: utf-8 -*-
"""Helpers for CLI stdout/stderr contracts."""

from __future__ import annotations

import json
import sys
from typing import Any

from src.utils.stdout_guard import install_stdout_guard


install_stdout_guard()


def emit_stdout(message: str) -> None:
    print(message)


def emit_stderr(message: str) -> None:
    print(message, file=sys.stderr)


def emit_progress(message: str) -> None:
    emit_stdout(message)


def emit_error(message: str) -> None:
    emit_stderr(message)


def emit_json_stdout(payload: Any) -> None:
    emit_stdout(json.dumps(payload, ensure_ascii=False, indent=2))
