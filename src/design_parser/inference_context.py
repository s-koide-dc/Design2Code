"""Explicit input state for deterministic line-inference decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InferenceContext:
    step_index: int
    module_name: str
    last_output_type: str | None
    output_format: str
    is_last_step: bool
    last_persist_path: str | None
    semantic_roles: dict[str, Any]
    data_sources: tuple[dict[str, Any], ...]
