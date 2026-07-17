"""Deterministic source selection for design-inference fallbacks."""

from __future__ import annotations

from typing import Callable

from src.utils.semantic_intents import INTENT_FETCH, INTENT_FILE_IO, INTENT_HTTP_REQUEST


def collect_source_kinds(sources: list[dict[str, str]] | None) -> tuple[list[dict[str, str]], list[dict[str, str]], list[dict[str, str]], list[dict[str, str]]]:
    available = sources or []
    return (
        [source for source in available if source.get("kind") == "env"],
        [source for source in available if source.get("kind") == "stdin"],
        [source for source in available if source.get("kind") == "http"],
        [source for source in available if source.get("kind") == "file"],
    )


def select_source_override(
    line: str,
    step_index: int,
    env_sources: list[dict[str, str]],
    stdin_sources: list[dict[str, str]],
    http_sources: list[dict[str, str]],
    file_sources: list[dict[str, str]],
    extract_url: Callable[[str], str],
) -> tuple[str, str, str | None] | None:
    text = str(line)
    for source in env_sources:
        source_id = source.get("id")
        if source_id and source_id in text:
            return source_id, "env", INTENT_FETCH
    if len(env_sources) == 1 and not http_sources and not file_sources and not stdin_sources:
        return env_sources[0].get("id", "env"), "env", INTENT_FETCH
    if step_index == 1 and len(stdin_sources) == 1 and not http_sources and not file_sources:
        return stdin_sources[0].get("id", "STDIN"), "stdin", INTENT_FETCH
    for source in file_sources:
        source_id = str(source.get("id") or "")
        if source_id == "input_path" and "入力ファイルパス" in text:
            return source_id, "file", INTENT_FETCH
        if source_id == "output_path" and "出力ファイルパス" in text:
            return source_id, "file", INTENT_FILE_IO
    if len(http_sources) == 1 and extract_url(text):
        return http_sources[0].get("id", "http_main"), "http", INTENT_HTTP_REQUEST
    return None
