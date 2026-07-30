"""Expand a deliberately small, unambiguous shorthand for ACTION steps."""
from __future__ import annotations

from dataclasses import dataclass

from src.design_parser.inference_line_syntax import find_bracket_end, strip_leading_numbering


@dataclass(frozen=True)
class CompactStepError:
    line_number: int
    detail: str


_ACTION_EFFECTS = {
    "FETCH": "IO",
    "FILE_IO": "IO",
    "PERSIST": "IO",
    "HTTP_REQUEST": "NETWORK",
    "JSON_DESERIALIZE": "NONE",
    "LINQ": "NONE",
    "TRANSFORM": "NONE",
    "CALC": "NONE",
    "DISPLAY": "NONE",
    "RETURN": "NONE",
}
_SOURCE_REQUIRED = {"FETCH", "FILE_IO", "PERSIST", "HTTP_REQUEST"}
_SOURCE_KINDS = {"db", "env", "file", "http", "memory", "stdin"}


def _expand_step(text: str) -> tuple[str | None, str | None]:
    stripped = strip_leading_numbering(text)
    if not stripped.startswith("[step|"):
        return text, None
    end = find_bracket_end(stripped)
    if end < 0:
        return None, "compact step tag is not closed"
    fields = [field.strip() for field in stripped[1:end].split("|")]
    if len(fields) < 4 or fields[0] != "step":
        return None, "compact step requires [step|INTENT|TARGET|OUTPUT|...]"
    _, intent, target, output, *options = fields
    if intent not in _ACTION_EFFECTS or not target or not output:
        return None, "compact step intent, target, and output must be explicitly supported and non-empty"
    values: dict[str, str] = {}
    for option in options:
        if "=" not in option:
            return None, "compact step options must use key=value"
        key, value = (part.strip() for part in option.split("=", 1))
        if key not in {"source", "source_kind"} or not value or key in values:
            return None, "compact step permits unique source and source_kind options only"
        values[key] = value
    has_source = "source" in values or "source_kind" in values
    if intent in _SOURCE_REQUIRED and set(values) != {"source", "source_kind"}:
        return None, f"{intent} requires source and source_kind"
    if intent not in _SOURCE_REQUIRED and has_source:
        return None, f"{intent} does not accept source options in compact form"
    if "source_kind" in values and values["source_kind"] not in _SOURCE_KINDS:
        return None, "source_kind is not supported"
    expanded = f"[ACTION|{intent}|{target}|{output}|{_ACTION_EFFECTS[intent]}"
    if intent in _SOURCE_REQUIRED:
        expanded += f"|{values['source']}|{values['source_kind']}"
    expanded += "]"
    prefix_length = len(text) - len(stripped)
    return text[:prefix_length] + expanded + stripped[end + 1:], None


def expand_compact_steps(content: str) -> tuple[str, list[CompactStepError]]:
    """Expand [step|...] only inside Core Logic; leave all other text untouched."""
    errors: list[CompactStepError] = []
    output: list[str] = []
    in_core_logic = False
    for line_number, line in enumerate(content.splitlines(keepends=True), start=1):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        lowered = body.strip().lower()
        if lowered.startswith("### core logic"):
            in_core_logic = True
        elif in_core_logic and lowered.startswith("### "):
            in_core_logic = False
        if in_core_logic:
            expanded, error = _expand_step(body)
            if error:
                errors.append(CompactStepError(line_number, error))
            output.append((expanded if expanded is not None else body) + ending)
        else:
            output.append(line)
    return "".join(output), errors
