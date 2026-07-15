"""Normalization of action results consumed by the dialogue layer."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


class ActionResultMetadata:
    def __init__(self, entity_value_resolver: Callable[[Any], Any]):
        self._resolve_entity = entity_value_resolver

    def augment(self, context: dict, action_method_name: str, parameters: Mapping[str, Any]) -> None:
        action_result = context.get("action_result")
        if not isinstance(action_result, dict):
            return

        dialogue_metadata = action_result.get("dialogue_metadata")
        if not isinstance(dialogue_metadata, dict):
            dialogue_metadata = {}
            action_result["dialogue_metadata"] = dialogue_metadata

        dialogue_metadata.setdefault("action_method", action_method_name)
        dialogue_metadata.setdefault("intent", context.get("analysis", {}).get("intent"))

        for key in ("filename", "source_filename", "destination_filename", "project_path", "goal_description"):
            if key not in dialogue_metadata:
                value = self._resolve_entity(parameters.get(key))
                if value:
                    dialogue_metadata[key] = value

        if "target_name" not in action_result:
            for key in ("filename", "project_path", "goal_description"):
                value = self._resolve_entity(parameters.get(key))
                if value:
                    action_result["target_name"] = value
                    break
