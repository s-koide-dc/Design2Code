# -*- coding: utf-8 -*-
from typing import Dict


def parse_data_source_tag(text: str, allowed_kinds: set[str]) -> Dict[str, str]:
    raw = str(text).strip()
    if raw.startswith("- "):
        raw = raw[2:].strip()
    if not raw.startswith("[data_source|"):
        return {}
    end = raw.find("]")
    if end == -1:
        return {}
    tag = raw[1:end]
    parts = [p.strip() for p in tag.split("|")]
    if len(parts) < 3:
        return {}
    source_id = parts[1]
    source_kind = parts[2].lower()
    if not source_id or not source_kind:
        return {}
    if source_kind not in allowed_kinds:
        return {}
    return {"id": source_id, "kind": source_kind}
