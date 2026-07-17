"""Collect deterministic data-source declarations from Core Logic lines."""

from __future__ import annotations

from typing import Any, Callable


def collect_data_sources(core_logic: list[str], resolve_data_source_tag: Callable[[str], str]) -> list[str]:
    sources: list[str] = []
    for line in core_logic:
        source = resolve_data_source_tag(line)
        if source:
            sources.append(source)
    return sources


def build_file_source_ref(value: str) -> str:
    leaf = str(value).strip().replace("\\", "/").rsplit("/", 1)[-1]
    if not leaf:
        return ""
    characters: list[str] = []
    previous_was_separator = False
    for character in leaf:
        if character.isalnum():
            characters.append(character.lower())
            previous_was_separator = False
        elif not previous_was_separator:
            characters.append("_")
            previous_was_separator = True
    return "".join(characters).strip("_") or "file_source"


def infer_plain_data_source_tag(line: str, profiles: list[dict[str, str]], io_inputs: list[dict[str, Any]], is_likely_filename: Callable[[str], bool]) -> str:
    normalized = str(line).strip()
    for profile in profiles:
        if normalized == profile["text"]:
            return f'[data_source|{profile["source_ref"]}|{profile["source_kind"]}]'
    if is_likely_filename(normalized):
        return f"[data_source|{build_file_source_ref(normalized)}|file]"
    aliases = {"入力CSV": "input_path", "出力CSV": "output_path"}
    expected_name = aliases.get(normalized)
    if expected_name and any(str(item.get("name") or "").strip() == expected_name for item in io_inputs):
        return f"[data_source|{expected_name}|file]"
    return ""
