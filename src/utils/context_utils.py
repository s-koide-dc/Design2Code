import os

def normalize_path(path: str) -> str:
    """パスを標準化する（Windowsの区切り文字、重複するスラッシュなどを解消）"""
    if not path: return ""
    # 前後の空白と引用符を除去
    path = path.strip().strip("'\"「」『』")
    # Windowsのバックスラッシュをスラッシュに統一（内部処理用）
    normalized = path.replace('\\\\', '/').replace('\\', '/')
    # 不要な重複スラッシュを除去
    while '//' in normalized:
        normalized = normalized.replace('//', '/')
    return normalized

def extract_path_from_text(text: str) -> str | None:
    """テキストからパスと思われる文字列を抽出する"""
    if not text:
        return None
    candidates = []
    quoted = _extract_quoted_candidates(text)
    candidates.extend(quoted)
    candidates.extend(_extract_tokens(text))
    for c in candidates:
        if _looks_like_path(c):
            return normalize_path(c)
    return None

def _extract_quoted_candidates(text: str) -> list[str]:
    pairs = [("「", "」"), ("『", "』"), ("\"", "\""), ("'", "'"), ("(", ")")]
    results = []
    s = str(text)
    for open_q, close_q in pairs:
        start = 0
        while True:
            idx = s.find(open_q, start)
            if idx == -1:
                break
            end = s.find(close_q, idx + len(open_q))
            if end == -1:
                break
            literal = s[idx + len(open_q):end].strip()
            if literal:
                results.append(literal)
            start = end + len(close_q)
    return results

def _extract_tokens(text: str) -> list[str]:
    tokens = []
    current = []
    for ch in str(text):
        if ch.isalnum() or ch in ['_', '-', '.', '/', '\\', ':']:
            current.append(ch)
        else:
            if current:
                tokens.append("".join(current))
                current = []
    if current:
        tokens.append("".join(current))
    return tokens

def _looks_like_path(token: str) -> bool:
    if not token:
        return False
    t = token.strip()
    if len(t) < 3:
        return False
    if ":" in t and "\\" in t:
        return True
    if ":" in t and "/" in t:
        return True
    if "/" in t or "\\" in t:
        return True
    if "." in t:
        # basic extension check: last segment contains dot and alphabetic suffix
        last = t.split("/")[-1].split("\\")[-1]
        if "." in last:
            ext = last.split(".")[-1]
            return ext.isalnum()
    return False

def _get_context_summary(context: dict | None) -> dict:
    if context is None:
        return {
            "intent": "NoneContext",
            "intent_confidence": 0.0,
            "entities": {},
            "plan_action": "None",
            "action_result_status": "None",
            "response_text_preview": "Context was None",
            "errors": [{"module": "pipeline_core", "message": "Context object was None"}]
        }
        
    plan = context.get("plan", {})
    if plan is None:
        plan = {}
        
    summary = {
        "intent": context.get("analysis", {}).get("intent"),
        "intent_confidence": context.get("analysis", {}).get("intent_confidence"),
        "entities": {k: v.get("value") for k, v in context.get("analysis", {}).get("entities", {}).items() if isinstance(v, dict)},
        "plan_action": plan.get("action_method"),
        "action_result_status": context.get("action_result", {}).get("status"),
        "response_text_preview": context.get("response", {}).get("text", "")[:100],
        "errors": context.get("errors", [])
    }
    return summary
