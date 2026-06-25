# -*- coding: utf-8 -*-
"""Probe how far stripped .design.md variants can still be inferred and generated."""
from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict, List, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.append(str(WORKSPACE_ROOT))

from src.design_parser import infer_then_freeze_if_needed
from scripts.strip_design_tags import strip_design_tags

logging.getLogger("SemanticSearch.structural_memory").setLevel(logging.ERROR)


def _is_step_line(text: str) -> bool:
    stripped = str(text).lstrip()
    i = 0
    while i < len(stripped) and stripped[i].isdigit():
        i += 1
    return i > 0 and i < len(stripped) and stripped[i] == "."


def _find_core_logic_range(lines: List[str]) -> Tuple[int, int]:
    start = -1
    end = len(lines)
    for idx, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped.startswith("### core logic"):
            start = idx + 1
            continue
        if start != -1 and idx >= start and (stripped.startswith("## ") or stripped.startswith("### ")):
            end = idx
            break
    return start, end


def _remove_quoted_literals_from_text(text: str) -> str:
    out: List[str] = []
    in_quote = False
    quote_char = ""
    for ch in str(text):
        if in_quote:
            if ch == quote_char:
                in_quote = False
                quote_char = ""
            continue
        if ch in ["'", '"']:
            in_quote = True
            quote_char = ch
            continue
        out.append(ch)
    collapsed = " ".join("".join(out).split())
    return collapsed


def _transform_core_logic(content: str, transformer: Callable[[str], str], *, drop_empty: bool = False) -> str:
    lines = content.splitlines()
    start, end = _find_core_logic_range(lines)
    if start == -1:
        return content
    updated: List[str] = []
    for idx, line in enumerate(lines):
        if idx < start or idx >= end:
            updated.append(line)
            continue
        new_line = transformer(line)
        if drop_empty and not new_line.strip():
            continue
        updated.append(new_line)
    return "\n".join(updated) + ("\n" if content.endswith("\n") else "")


def _drop_plain_source_lines(content: str) -> str:
    def _transform(line: str) -> str:
        stripped = line.strip()
        if not stripped:
            return line
        if stripped.startswith("- "):
            return line
        if _is_step_line(stripped):
            return line
        return ""

    return _transform_core_logic(content, _transform, drop_empty=True)


def _drop_literals_from_core_logic(content: str) -> str:
    def _transform(line: str) -> str:
        stripped = line.strip()
        if not stripped:
            return line
        if stripped.startswith("### "):
            return line
        prefix_len = len(line) - len(line.lstrip())
        prefix = line[:prefix_len]
        transformed = _remove_quoted_literals_from_text(line[prefix_len:])
        return prefix + transformed

    return _transform_core_logic(content, _transform)


def _variant_original(content: str) -> str:
    return content


def _variant_strip_tags(content: str) -> str:
    return strip_design_tags(content)


def _variant_strip_tags_drop_literals(content: str) -> str:
    return _drop_literals_from_core_logic(strip_design_tags(content))


def _variant_strip_tags_drop_plain_sources(content: str) -> str:
    return _drop_plain_source_lines(strip_design_tags(content))


def _variant_strip_tags_drop_literals_and_plain_sources(content: str) -> str:
    return _drop_plain_source_lines(_drop_literals_from_core_logic(strip_design_tags(content)))


VARIANTS: List[Tuple[str, Callable[[str], str]]] = [
    ("original", _variant_original),
    ("strip_tags", _variant_strip_tags),
    ("strip_tags_drop_literals", _variant_strip_tags_drop_literals),
    ("strip_tags_drop_plain_sources", _variant_strip_tags_drop_plain_sources),
    ("strip_tags_drop_literals_and_plain_sources", _variant_strip_tags_drop_literals_and_plain_sources),
]


def _module_basename(design_path: Path) -> str:
    name = design_path.name
    if name.endswith(".design.md"):
        return name[:-10]
    return design_path.stem


def _run_generation(design_path: Path, output_path: Path) -> Dict[str, object]:
    command = [
        sys.executable,
        "scripts/generate/generate_from_design.py",
        "--design",
        str(design_path),
        "--output",
        str(output_path),
    ]
    completed = subprocess.run(
        command,
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "generated": completed.returncode == 0 and output_path.exists(),
        "clean_generate": completed.returncode == 0 and output_path.exists() and not completed.stderr.strip(),
    }


def _read_excerpt(path: Path, max_lines: int = 12) -> List[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()[:max_lines]


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe stripped design inference/generation boundaries.")
    parser.add_argument("--design", required=True, help="Input .design.md path")
    parser.add_argument("--output-dir", required=False, help="Output directory for probe artifacts")
    args = parser.parse_args()

    design_path = Path(args.design)
    if not design_path.exists():
        print(json.dumps({"error": f"Design document not found: {design_path}"}, ensure_ascii=False), file=sys.stderr)
        return 1

    content = design_path.read_text(encoding="utf-8")
    probe_root = Path(args.output_dir) if args.output_dir else WORKSPACE_ROOT / "cache" / f"{design_path.stem}.boundary_probe"
    if probe_root.exists():
        shutil.rmtree(probe_root)
    probe_root.mkdir(parents=True, exist_ok=True)

    results: List[Dict[str, object]] = []
    for variant_name, transform in VARIANTS:
        variant_dir = probe_root / variant_name
        variant_dir.mkdir(parents=True, exist_ok=True)
        variant_design = variant_dir / design_path.name
        variant_output = variant_dir / f"{_module_basename(design_path)}.cs"
        variant_design.write_text(transform(content), encoding="utf-8")

        inference_result = infer_then_freeze_if_needed(str(variant_design))
        inferred_path_str = str(inference_result.get("output_path") or "").strip()
        inferred_path = Path(inferred_path_str) if inferred_path_str else None
        generation_result = _run_generation(variant_design, variant_output)

        results.append(
            {
                "variant": variant_name,
                "design_path": str(variant_design),
                "inference_status": inference_result.get("status"),
                "inference_message": inference_result.get("message"),
                "issues": inference_result.get("issues", []),
                "inferred_design_path": str(inferred_path) if inferred_path is not None else "",
                "inferred_design_exists": inferred_path.exists() if inferred_path is not None else False,
                "generated": bool(generation_result["generated"]),
                "clean_generate": bool(generation_result["clean_generate"]),
                "generate_returncode": generation_result["returncode"],
                "generate_stdout": generation_result["stdout"],
                "generate_stderr": generation_result["stderr"],
                "inferred_excerpt": _read_excerpt(inferred_path) if inferred_path is not None else [],
            }
        )

    payload = {
        "design": str(design_path),
        "probe_root": str(probe_root),
        "variants": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
