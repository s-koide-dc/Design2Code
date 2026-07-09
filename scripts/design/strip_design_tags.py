# -*- coding: utf-8 -*-
"""Create a tag-stripped .design.md variant for inference evaluation."""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Tuple


def _split_line_prefix(line: str) -> Tuple[str, str]:
    s = line.rstrip("\n")
    stripped = s.lstrip()
    prefix_len = len(s) - len(stripped)
    prefix = s[:prefix_len]
    if stripped.startswith("- "):
        return prefix + "- ", stripped[2:].strip()
    i = 0
    while i < len(stripped) and stripped[i].isdigit():
        i += 1
    if i > 0 and i < len(stripped) and stripped[i] == ".":
        if i + 1 < len(stripped) and stripped[i + 1] == " ":
            return prefix + stripped[: i + 2], stripped[i + 2 :].strip()
    return prefix, stripped.strip()


def _extract_bracket_prefix(text: str) -> Tuple[str, str]:
    s = str(text).lstrip()
    if not s.startswith("["):
        return "", text
    end = _find_bracket_end(s)
    if end == -1:
        return "", text
    meta = s[1:end].strip()
    remainder = s[end + 1 :].strip()
    return meta, remainder


def _find_bracket_end(text: str) -> int:
    in_string = False
    escape = False
    nested_square = 0
    for idx in range(1, len(text)):
        ch = text[idx]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "[":
            nested_square += 1
            continue
        if ch == "]":
            if nested_square == 0:
                return idx
            nested_square -= 1
    return -1


def _looks_like_step_meta(meta: str) -> bool:
    if not meta:
        return False
    head = meta.split("|", 1)[0].strip().upper()
    return head in {"ACTION", "CONDITION", "LOOP", "ELSE", "END"}


def _is_strip_target(meta: str) -> bool:
    lowered = meta.lower()
    if lowered.startswith("refs:"):
        return True
    if lowered.startswith("ops:"):
        return True
    if lowered.startswith("semantic_roles:"):
        return True
    if lowered.startswith("data_source|"):
        return True
    return _looks_like_step_meta(meta)


def _strip_core_logic_line(line: str) -> str:
    prefix, remainder = _split_line_prefix(line)
    text = remainder
    while True:
        meta, updated = _extract_bracket_prefix(text)
        if not meta or not _is_strip_target(meta):
            break
        text = updated
    text = text.strip()
    if not text:
        return ""
    return f"{prefix}{text}"


def strip_design_tags(content: str) -> str:
    lines = content.splitlines()
    out_lines: List[str] = []
    in_core_logic = False
    in_inference_metadata = False

    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()

        if stripped == "### Inference Metadata":
            in_inference_metadata = True
            continue
        if in_inference_metadata:
            if stripped.startswith("## ") or stripped.startswith("### "):
                in_inference_metadata = False
            else:
                continue

        if lowered.startswith("### core logic"):
            in_core_logic = True
            out_lines.append(line)
            continue
        if in_core_logic and (lowered.startswith("## ") or lowered.startswith("### ")) and not lowered.startswith("### core logic"):
            in_core_logic = False

        if in_core_logic:
            stripped_line = _strip_core_logic_line(line)
            if stripped_line:
                out_lines.append(stripped_line)
            continue

        out_lines.append(line)

    return "\n".join(out_lines) + ("\n" if content.endswith("\n") else "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Strip explicit bracket tags from .design.md core logic.")
    parser.add_argument("--design", required=True, help="Input .design.md path")
    parser.add_argument("--output", required=True, help="Output stripped .design.md path")
    args = parser.parse_args()

    if not os.path.exists(args.design):
        print(f"Design document not found: {args.design}", file=sys.stderr)
        return 1

    with open(args.design, "r", encoding="utf-8") as f:
        content = f.read()

    stripped = strip_design_tags(content)
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(stripped)

    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
