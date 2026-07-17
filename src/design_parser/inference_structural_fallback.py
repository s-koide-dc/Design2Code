"""Ordered source-oriented fallback dispatch for design inference."""

from __future__ import annotations

from typing import Any


def resolve_source_fallback(engine: Any, line: str, step_index: int, env_sources: list[dict], stdin_sources: list[dict], http_sources: list[dict], file_sources: list[dict]) -> tuple[dict | None, dict]:
    meta = engine._infer_plain_stdin_fetch_meta(line, step_index, stdin_sources)
    if meta:
        return meta, {}
    meta = engine._infer_plain_env_fetch_meta(line, env_sources)
    if meta:
        return meta, {}
    meta, roles = engine._infer_plain_http_request_meta(line, http_sources)
    if meta:
        return meta, roles
    meta, roles = engine._infer_plain_file_source_fetch_meta(line, file_sources)
    if meta:
        return meta, roles
    return engine._infer_plain_file_fetch_meta(line)
