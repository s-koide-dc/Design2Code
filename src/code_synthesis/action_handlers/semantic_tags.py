from typing import Dict, List


def load_domain_tags(synthesizer) -> Dict[str, List[str]]:
    config = getattr(synthesizer, "config", None)
    path = getattr(config, "domain_dictionary_path", None) if config else None
    if not path:
        return {}
    if not synthesizer or not path:
        return {}
    try:
        import os
        import json
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        tags = data.get("tags", {})
        return tags if isinstance(tags, dict) else {}
    except Exception:
        return {}


def has_tag(synthesizer, domain_tags: Dict[str, List[str]], text: str, tag: str) -> bool:
    tokens = domain_tags.get(tag, [])
    if not tokens or not text:
        return False
    token_hits: List[str] = []
    analyzer = getattr(synthesizer, "morph_analyzer", None)
    if analyzer:
        try:
            res = analyzer.analyze({"original_text": text})
            token_list = res.get("analysis", {}).get("tokens", []) if isinstance(res, dict) else []
            for t in token_list:
                if not isinstance(t, dict):
                    continue
                surface = t.get("surface")
                base = t.get("base_form")
                if surface:
                    token_hits.append(str(surface).lower())
                if base and base != surface:
                    token_hits.append(str(base).lower())
        except Exception:
            token_hits = []
    if token_hits:
        for token in tokens:
            if not token:
                continue
            t_lower = str(token).lower()
            if any(t_lower == hit or t_lower in hit for hit in token_hits):
                return True
    for token in tokens:
        if not token:
            continue
        if str(token).lower() in text.lower():
            return True
    return False
