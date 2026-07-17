"""Syntax helpers for deterministic design-inference metadata parsing."""

from __future__ import annotations


def find_bracket_end(text: str) -> int:
    in_string = False
    escape = False
    nested_square = 0
    for index in range(1, len(text)):
        character = text[index]
        if escape:
            escape = False
            continue
        if character == "\\":
            escape = True
            continue
        if character == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if character == "[":
            nested_square += 1
            continue
        if character == "]":
            if nested_square == 0:
                return index
            nested_square -= 1
    return -1


def strip_leading_numbering(text: str) -> str:
    value = text.strip()
    index = 0
    while index < len(value) and value[index].isdigit():
        index += 1
    if index > 0 and index < len(value) and value[index] == "." and index + 1 < len(value) and value[index + 1].isspace():
        return value[index + 2:].strip()
    if value.startswith("- "):
        return value[2:].strip()
    return value
