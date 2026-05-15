# -*- coding: utf-8 -*-
from typing import Any, Dict, List, Optional


DEFAULT_RETRY_ATTEMPTS = 3
DEFAULT_RETRY_EXCEPTION_TYPE = "Exception"
DEFAULT_RETRY_BASE_DELAY_MS = 0
DEFAULT_RETRY_BACKOFF_MULTIPLIER = 1.0
DEFAULT_TIMEOUT_MS = 30000


def normalize_retry_attempts(value: Any) -> Optional[int]:
    try:
        attempts = int(value)
    except (TypeError, ValueError):
        return None
    if attempts < 1:
        return 1
    return attempts


def normalize_timeout_ms(value: Any) -> Optional[int]:
    try:
        timeout_ms = int(value)
    except (TypeError, ValueError):
        return None
    if timeout_ms < 1:
        return 1
    return timeout_ms


def has_wrapper_metadata_hint(semantic_roles: Dict[str, Any]) -> bool:
    roles = semantic_roles or {}
    if isinstance(roles.get("wrapper_kind"), str) and roles.get("wrapper_kind", "").strip():
        return True
    wrapper_keys = {
        "max_attempts",
        "max_retries",
        "retry_count",
        "exception_type",
        "catch_exception_type",
        "retry_exception_type",
        "base_delay_ms",
        "delay_ms",
        "retry_delay_ms",
        "max_delay_ms",
        "retry_max_delay_ms",
        "backoff_multiplier",
        "retry_backoff_multiplier",
        "timeout_ms",
        "max_duration_ms",
        "duration_ms",
    }
    return any(key in roles for key in wrapper_keys)


def infer_wrapper_metadata(
    tokens: List[Dict[str, Any]],
    semantic_roles: Dict[str, Any],
) -> Dict[str, Any]:
    resolved_roles = dict(semantic_roles or {})
    resolved_roles.setdefault("structure_kind", "wrapper")

    wrapper_kind = str(resolved_roles.get("wrapper_kind") or "").strip().lower()
    if wrapper_kind == "timeout":
        return infer_timeout_wrapper_metadata(resolved_roles)
    if wrapper_kind == "transaction":
        return infer_transaction_wrapper_metadata(resolved_roles)

    retry_metadata_present = any(
        key in resolved_roles
        for key in [
            "max_attempts",
            "max_retries",
            "retry_count",
            "exception_type",
            "catch_exception_type",
            "retry_exception_type",
            "base_delay_ms",
            "delay_ms",
            "retry_delay_ms",
            "max_delay_ms",
            "retry_max_delay_ms",
            "backoff_multiplier",
            "retry_backoff_multiplier",
        ]
    )
    if wrapper_kind == "retry" or retry_metadata_present or _looks_retry_wrapper(tokens):
        return infer_retry_wrapper_metadata(tokens, resolved_roles)

    if not wrapper_kind:
        resolved_roles["wrapper_kind"] = "wrapper"
    return resolved_roles


def infer_retry_wrapper_metadata(
    tokens: List[Dict[str, Any]],
    semantic_roles: Dict[str, Any],
) -> Dict[str, Any]:
    resolved_roles = dict(semantic_roles or {})
    resolved_roles.setdefault("wrapper_kind", "retry")
    resolved_roles.setdefault("structure_kind", "wrapper")

    explicit_attempts = (
        resolved_roles.get("max_attempts")
        or resolved_roles.get("max_retries")
        or resolved_roles.get("retry_count")
    )
    normalized_attempts = normalize_retry_attempts(explicit_attempts)
    attempts_resolution = None
    if normalized_attempts is None:
        normalized_attempts = _infer_attempts_from_tokens(tokens)
        if normalized_attempts is not None:
            attempts_resolution = "token_attempts"
    else:
        attempts_resolution = "explicit_attempts"
    if normalized_attempts is None:
        normalized_attempts = DEFAULT_RETRY_ATTEMPTS
        attempts_resolution = "default_attempts"
    resolved_roles["max_attempts"] = normalized_attempts
    resolved_roles["max_attempts_resolution"] = attempts_resolution

    exception_type = (
        resolved_roles.get("exception_type")
        or resolved_roles.get("catch_exception_type")
        or resolved_roles.get("retry_exception_type")
    )
    if isinstance(exception_type, str) and exception_type.strip():
        resolved_roles["exception_type"] = exception_type.strip()
        resolved_roles["exception_type_resolution"] = "explicit_exception_type"
    else:
        resolved_roles["exception_type"] = DEFAULT_RETRY_EXCEPTION_TYPE
        resolved_roles["exception_type_resolution"] = "default_exception_type"

    delay_policy_explicit = False
    base_delay_ms = _normalize_non_negative_int(
        resolved_roles.get("base_delay_ms")
        or resolved_roles.get("delay_ms")
        or resolved_roles.get("retry_delay_ms")
    )
    if base_delay_ms is not None:
        delay_policy_explicit = True
        resolved_roles["base_delay_ms"] = base_delay_ms
    else:
        resolved_roles["base_delay_ms"] = DEFAULT_RETRY_BASE_DELAY_MS

    max_delay_ms = _normalize_non_negative_int(
        resolved_roles.get("max_delay_ms")
        or resolved_roles.get("retry_max_delay_ms")
    )
    if max_delay_ms is not None:
        delay_policy_explicit = True
        resolved_roles["max_delay_ms"] = max_delay_ms

    backoff_multiplier = _normalize_min_float(
        resolved_roles.get("backoff_multiplier")
        or resolved_roles.get("retry_backoff_multiplier"),
        1.0,
    )
    if backoff_multiplier is not None:
        delay_policy_explicit = True
        resolved_roles["backoff_multiplier"] = backoff_multiplier
    else:
        resolved_roles["backoff_multiplier"] = DEFAULT_RETRY_BACKOFF_MULTIPLIER

    if delay_policy_explicit:
        resolved_roles["retry_delay_policy_resolution"] = "explicit_delay_policy"
    else:
        resolved_roles["retry_delay_policy_resolution"] = "default_no_delay_policy"

    return resolved_roles


def infer_timeout_wrapper_metadata(
    semantic_roles: Dict[str, Any],
) -> Dict[str, Any]:
    resolved_roles = dict(semantic_roles or {})
    resolved_roles["wrapper_kind"] = "timeout"
    resolved_roles.setdefault("structure_kind", "wrapper")

    explicit_timeout = (
        resolved_roles.get("timeout_ms")
        or resolved_roles.get("max_duration_ms")
        or resolved_roles.get("duration_ms")
    )
    normalized_timeout = normalize_timeout_ms(explicit_timeout)
    if normalized_timeout is None:
        normalized_timeout = DEFAULT_TIMEOUT_MS
        timeout_resolution = "default_timeout_ms"
    else:
        timeout_resolution = "explicit_timeout_ms"
    resolved_roles["timeout_ms"] = normalized_timeout
    resolved_roles["timeout_resolution"] = timeout_resolution
    return resolved_roles


def infer_transaction_wrapper_metadata(
    semantic_roles: Dict[str, Any],
) -> Dict[str, Any]:
    resolved_roles = dict(semantic_roles or {})
    resolved_roles["wrapper_kind"] = "transaction"
    resolved_roles.setdefault("structure_kind", "wrapper")
    resolved_roles["transaction_resolution"] = "explicit_transaction_wrapper"
    return resolved_roles


def _infer_attempts_from_tokens(tokens: List[Dict[str, Any]]) -> Optional[int]:
    surfaces = [str(t.get("surface") or "") for t in (tokens or [])]
    if not surfaces:
        return None
    for i, surface in enumerate(surfaces[:-1]):
        attempts = normalize_retry_attempts(surface)
        if attempts is None:
            continue
        if surfaces[i + 1] == "回":
            return attempts
    return None


def _looks_retry_wrapper(tokens: List[Dict[str, Any]]) -> bool:
    surfaces = [str(t.get("surface") or "") for t in (tokens or [])]
    bases = [str(t.get("base") or "") for t in (tokens or [])]
    if "リトライ" in surfaces:
        return True
    if "再試行" in bases:
        return True
    for seq in (surfaces, bases):
        for i in range(0, len(seq) - 1):
            if seq[i:i + 2] == ["再", "試行"]:
                return True
    return False


def _normalize_non_negative_int(value: Any) -> Optional[int]:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        return None
    if normalized < 0:
        return 0
    return normalized


def _normalize_min_float(value: Any, minimum: float) -> Optional[float]:
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return None
    if normalized < minimum:
        return minimum
    return normalized
