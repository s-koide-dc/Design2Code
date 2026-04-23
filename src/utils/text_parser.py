# -*- coding: utf-8 -*-
from typing import List, Optional
from urllib.parse import urlparse


def extract_urls(text: Optional[str]) -> List[str]:
    if not text:
        return []
    cleaned = (
        str(text)
        .replace("(", " ")
        .replace(")", " ")
        .replace("（", " ")
        .replace("）", " ")
    )
    tokens = cleaned.split()
    urls: List[str] = []
    for token in tokens:
        t = token.strip("\"'<>[]{}")
        if not t:
            continue
        if t.startswith("http://") or t.startswith("https://"):
            parsed = urlparse(t)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                urls.append(t)
            continue
        if t.startswith("www."):
            parsed = urlparse("http://" + t)
            if parsed.netloc:
                urls.append(t)
    return urls


def extract_sql_params(sql_text: Optional[str]) -> List[str]:
    if not sql_text:
        return []
    text = str(sql_text)
    params: List[str] = []
    i = 0
    while i < len(text):
        if text[i] == "@":
            j = i + 1
            if j < len(text) and _is_ident_start(text[j]):
                k = j + 1
                while k < len(text) and _is_ident_char(text[k]):
                    k += 1
                params.append(text[i:k])
                i = k
                continue
        i += 1
    return params


def _is_ident_start(ch: str) -> bool:
    return ch.isalpha() or ch == "_"


def _is_ident_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def extract_quoted_literals(text: Optional[str]) -> List[str]:
    if not text:
        return []
    pairs = [
        ("「", "」"),
        ("『", "』"),
        ("“", "”"),
        ("\"", "\""),
        ("'", "'"),
    ]
    s = str(text)
    results: List[str] = []
    for open_q, close_q in pairs:
        start = 0
        while True:
            idx = s.find(open_q, start)
            if idx == -1:
                break
            end = s.find(close_q, idx + len(open_q))
            if end == -1:
                break
            literal = s[idx + len(open_q):end]
            if literal:
                results.append(literal)
            start = end + len(close_q)
    return results


def extract_first_quoted_literal(text: Optional[str]) -> Optional[str]:
    literals = extract_quoted_literals(text)
    return literals[0] if literals else None


def contains_word(text: Optional[str], word: Optional[str]) -> bool:
    if not text or not word:
        return False
    t = str(text)
    w = str(word)
    start = 0
    while True:
        idx = t.find(w, start)
        if idx == -1:
            return False
        before = t[idx - 1] if idx > 0 else ""
        after_idx = idx + len(w)
        after = t[after_idx] if after_idx < len(t) else ""
        before_ok = (before == "" or not (before.isalnum() or before == "_"))
        after_ok = (after == "" or not (after.isalnum() or after == "_"))
        if before_ok and after_ok:
            return True
        start = idx + len(w)


def is_numeric_literal(value: Optional[str]) -> bool:
    if value is None:
        return False
    s = str(value).strip()
    if not s:
        return False
    if "." in s:
        parts = s.split(".")
        return len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit()
    return s.isdigit()


def extract_percentage_value(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    s = str(text)
    i = 0
    while i < len(s):
        if s[i].isdigit():
            j = i
            while j < len(s) and s[j].isdigit():
                j += 1
            if j < len(s) and s[j] == "%":
                try:
                    return int(s[i:j])
                except Exception:
                    return None
            i = j
        i += 1
    return None


def extract_decimal_value(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    s = str(text)
    i = 0
    while i < len(s):
        if s[i].isdigit():
            j = i
            while j < len(s) and s[j].isdigit():
                j += 1
            if j < len(s) and s[j] == ".":
                k = j + 1
                if k < len(s) and s[k].isdigit():
                    while k < len(s) and s[k].isdigit():
                        k += 1
                    return s[i:k]
            i = j
        i += 1
    return None
