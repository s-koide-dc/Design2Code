# -*- coding: utf-8 -*-
from typing import Dict, Any, List


def infer_target_entity(text: str, history: list, entity_schema: Dict[str, Any], morph_analyzer=None) -> str:
    context_entity = history[-1]["target_entity"] if history else "Item"
    entities = [ent.get("name") for ent in entity_schema.get("entities", []) if ent.get("name")] if isinstance(entity_schema, dict) else []

    tokens = []
    if morph_analyzer:
        try:
            res = morph_analyzer.analyze({"original_text": text})
            tokens = res.get("analysis", {}).get("tokens", []) if isinstance(res, dict) else []
        except Exception:
            tokens = []
    bases = [str(t.get("base")) for t in tokens if isinstance(t, dict) and t.get("base")]
    surfaces = [str(t.get("surface")) for t in tokens if isinstance(t, dict) and t.get("surface")]
    lower_text = str(text).lower()

    for ent in entity_schema.get("entities", []) if isinstance(entity_schema, dict) else []:
        ent_name = ent.get("name")
        if not ent_name:
            continue
        for kw in ent.get("keywords", []) or []:
            if not kw:
                continue
            kw_str = str(kw)
            if kw_str in bases or kw_str in surfaces:
                return ent_name
            kw_low = kw_str.lower()
            if kw_low and kw_low in lower_text:
                return ent_name

    if context_entity and context_entity != "Item":
        return context_entity
    if len(entities) == 1:
        return entities[0]
    return context_entity
