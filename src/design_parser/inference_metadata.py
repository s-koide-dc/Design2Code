"""Persistence and provenance helpers for deterministic design inference."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Callable


def write_back_inference(
    content: str,
    updated_core_logic: list[str],
    data_sources: list[str],
    is_data_source_line: Callable[[str], bool],
) -> str:
    filtered_core = [line for line in updated_core_logic if not is_data_source_line(line)]
    deduped_sources: list[str] = []
    for source in data_sources:
        if source and source not in deduped_sources:
            deduped_sources.append(source)

    out_lines: list[str] = []
    in_core = False
    logic_lines_consumed = 0
    inserted_data_sources = False
    for line in content.splitlines():
        lower = line.strip().lower()
        if lower.startswith("##") or lower.startswith("###"):
            if in_core:
                in_core = False
            if "core logic" in lower:
                in_core = True
                out_lines.append(line)
                continue
        if in_core:
            if not inserted_data_sources and deduped_sources:
                out_lines.extend(f"- {source}" for source in deduped_sources)
                inserted_data_sources = True
            if logic_lines_consumed < len(filtered_core):
                out_lines.append(filtered_core[logic_lines_consumed])
                logic_lines_consumed += 1
            continue
        out_lines.append(line)
    return "\n".join(out_lines) + ("\n" if content.endswith("\n") else "")


def upsert_inference_metadata(content: str, metadata_block: str) -> str:
    if "### Inference Metadata" in content:
        return _replace_inference_block(content, metadata_block)
    return _insert_inference_block(content, metadata_block)


def _replace_inference_block(content: str, block: str) -> str:
    out: list[str] = []
    in_block = False
    for line in content.splitlines():
        if line.strip() == "### Inference Metadata":
            in_block = True
            out.append(block.strip())
            continue
        if in_block:
            if line.strip().startswith("## ") or line.strip().startswith("### "):
                in_block = False
                out.append(line)
            continue
        out.append(line)
    return "\n".join(out) + ("\n" if content.endswith("\n") else "")


def _insert_inference_block(content: str, block: str) -> str:
    out: list[str] = []
    inserted = False
    in_purpose = False
    for line in content.splitlines():
        lower = line.strip().lower()
        if lower.startswith("## purpose"):
            in_purpose = True
            out.append(line)
            continue
        if in_purpose and (line.strip().startswith("## ") or line.strip().startswith("### ")):
            out.append(block.strip())
            inserted = True
            in_purpose = False
        out.append(line)
    if not inserted:
        out.append(block.strip())
    return "\n".join(out) + ("\n" if content.endswith("\n") else "")


def build_inference_metadata_block(
    content: str,
    assets: list[dict[str, Any]],
    inference_rules_version: str,
    assist_metadata: dict[str, Any] | None,
) -> str:
    fingerprint = compute_fingerprint(content, assets, inference_rules_version)
    lines = [
        "### Inference Metadata",
        "- inference_mode: infer_then_freeze",
        f"- inference_fingerprint: {fingerprint}",
        "- assets:",
    ]
    lines.extend(f"  - {asset['path']}" for asset in assets)
    assist = assist_metadata or {}
    applied_steps = assist.get("applied_steps") or []
    if applied_steps:
        lines.append("- llm_literal_assist: true")
        lines.append(f"- llm_literal_assist_mode: {assist.get('mode') or 'literal_roles_only'}")
        if assist.get("provider"):
            lines.append(f"- llm_literal_assist_provider: {assist['provider']}")
        if assist.get("model_id"):
            lines.append(f"- llm_literal_assist_model_id: {assist['model_id']}")
        lines.append("- llm_literal_assist_applied_steps: " + ", ".join(str(step) for step in applied_steps))
    return "\n".join(lines)


def collect_assets(config_manager: Any) -> list[dict[str, Any]]:
    paths = [
        config_manager.vector_model_path,
        config_manager.dictionary_db_path,
        os.path.join(config_manager.workspace_root, "config", "scoring_rules.json"),
        config_manager.method_store_path,
        os.path.join(config_manager.workspace_root, "config", "config.json"),
        os.path.join(config_manager.workspace_root, "config", "safety_policy.json"),
        os.path.join(config_manager.workspace_root, "config", "project_rules.json"),
        os.path.join(config_manager.workspace_root, "config", "retry_rules.json"),
    ]
    return [hash_asset(path) for path in sorted(set(paths))]


def hash_asset(path: str) -> dict[str, Any]:
    info = {"path": path, "size_bytes": 0, "sha256": ""}
    if not path or not os.path.exists(path):
        return info
    try:
        info["size_bytes"] = os.path.getsize(path)
        info["sha256"] = sha256_file(path)
    except OSError:
        return info
    return info


def compute_fingerprint(content: str, assets: list[dict[str, Any]], inference_rules_version: str) -> str:
    payload = {
        "design_text_normalized": normalize_design_text(content),
        "asset_versions": assets,
        "inference_rules_version": inference_rules_version,
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def normalize_design_text(content: str) -> str:
    text = content.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in text.split("\n"))
    return remove_inference_metadata_block(normalized)


def remove_inference_metadata_block(content: str) -> str:
    if "### Inference Metadata" not in content:
        return content
    out: list[str] = []
    in_block = False
    for line in content.splitlines():
        if line.strip() == "### Inference Metadata":
            in_block = True
            continue
        if in_block:
            if line.strip().startswith("## ") or line.strip().startswith("### "):
                in_block = False
                out.append(line)
            continue
        out.append(line)
    return "\n".join(out)


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
