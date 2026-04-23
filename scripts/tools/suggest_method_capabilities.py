# -*- coding: utf-8 -*-
"""
Suggest intent/capabilities/param_roles for method metadata.

Important:
- This script is a *suggestion assistant* only.
- It uses explicit, exact-match dictionaries (no regex, no keyword heuristics).
- Do NOT auto-apply results; human review is required.
"""
import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional


def load_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_key(value: str) -> str:
    return value.strip()


def build_exact_rules() -> Dict[str, Any]:
    """
    Exact match rules:
    - class_rules: class -> method -> suggestion
    - class_defaults: class -> default suggestion (used only if method key present in defaults list)
    """
    class_rules = {
        "System.IO.File": {
            "ReadAllText": {
                "intent": "FETCH",
                "capabilities": ["FILE_IO", "READ"],
                "param_roles": {"path": "path"},
            },
            "ReadAllLines": {
                "intent": "FETCH",
                "capabilities": ["FILE_IO", "READ"],
                "param_roles": {"path": "path"},
            },
            "WriteAllText": {
                "intent": "PERSIST",
                "capabilities": ["FILE_IO", "WRITE"],
                "param_roles": {"path": "path", "contents": "content"},
            },
            "WriteAllLines": {
                "intent": "PERSIST",
                "capabilities": ["FILE_IO", "WRITE"],
                "param_roles": {"path": "path"},
            },
            "ReadAllTextAsync": {
                "intent": "FETCH",
                "capabilities": ["FILE_IO", "READ"],
                "param_roles": {"path": "path"},
            },
            "WriteAllTextAsync": {
                "intent": "PERSIST",
                "capabilities": ["FILE_IO", "WRITE"],
                "param_roles": {"path": "path", "contents": "content"},
            },
            "Exists": {
                "intent": "EXISTS",
                "capabilities": ["FILE_IO", "EXISTS"],
                "param_roles": {"path": "path"},
            },
        },
        "System.Console": {
            "WriteLine": {
                "intent": "DISPLAY",
                "capabilities": ["DISPLAY"],
            },
            "Write": {
                "intent": "DISPLAY",
                "capabilities": ["DISPLAY"],
            },
            "ReadKey": {
                "intent": "FETCH",
                "capabilities": ["FETCH"],
            },
            "ResetColor": {
                "intent": "TRANSFORM",
                "capabilities": ["TRANSFORM"],
            },
            "SetBufferSize": {
                "intent": "TRANSFORM",
                "capabilities": ["TRANSFORM"],
            },
            "SetWindowPosition": {
                "intent": "TRANSFORM",
                "capabilities": ["TRANSFORM"],
            },
            "SetWindowSize": {
                "intent": "TRANSFORM",
                "capabilities": ["TRANSFORM"],
            },
        },
        "System.Net.Http.HttpClient": {
            "GetStringAsync": {
                "intent": "HTTP_REQUEST",
                "capabilities": ["HTTP_REQUEST", "FETCH"],
                "param_roles": {"requestUri": "url", "request": "url"},
            },
            "PostAsync": {
                "intent": "HTTP_REQUEST",
                "capabilities": ["HTTP_REQUEST", "PERSIST"],
                "param_roles": {"requestUri": "url", "content": "content"},
            },
        },
        "System.Text.Json.JsonSerializer": {
            "Serialize": {
                "intent": "TRANSFORM",
                "capabilities": ["TRANSFORM", "JSON_SERIALIZE"],
            },
            "Deserialize": {
                "intent": "TRANSFORM",
                "capabilities": ["TRANSFORM", "JSON_DESERIALIZE"],
            },
        },
        "System.Linq.Enumerable": {
            "Where": {"intent": "LINQ", "capabilities": ["LINQ", "TRANSFORM"]},
            "Select": {"intent": "LINQ", "capabilities": ["LINQ", "TRANSFORM"]},
            "ToList": {"intent": "LINQ", "capabilities": ["LINQ", "TRANSFORM"]},
            "Any": {"intent": "LINQ", "capabilities": ["LINQ", "TRANSFORM"]},
        },
        "System.IO.Path": {
            "Combine": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
            "GetFileName": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
            "GetDirectoryName": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
            "GetExtension": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
            "ChangeExtension": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
        },
        "System.Environment": {
            "GetEnvironmentVariable": {
                "intent": "FETCH",
                "capabilities": ["FETCH"],
                "param_roles": {"variable": "name"},
            }
        },
        "System.DateTime": {
            "Parse": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
            "ParseExact": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
        },
        "System.Guid": {
            "Parse": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
            "ParseExact": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
            "NewGuid": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
        },
        "System.Convert": {
            "FromBase64String": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
            "ToBase64String": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
            "ToInt32": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
            "ToInt64": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
            "ToDecimal": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
            "ToDouble": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
            "ToString": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
        },
        "System.Security.Cryptography.MD5": {
            "Create": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
        },
        "System.Security.Cryptography.SHA256": {
            "Create": {"intent": "TRANSFORM", "capabilities": ["TRANSFORM"]},
        },
    }
    return {"class_rules": class_rules}


def suggest_for_method(method: Dict[str, Any], rules: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    cls = normalize_key(method.get("class", ""))
    name = normalize_key(method.get("name", ""))
    if not cls or not name:
        return None
    class_rules = rules.get("class_rules", {})
    if cls not in class_rules:
        return None
    method_rules = class_rules[cls]
    if name not in method_rules:
        return None
    return method_rules[name]


def main() -> int:
    root = os.getcwd()
    store_path = os.path.join(root, "resources", "method_store.json")
    map_path = os.path.join(root, "resources", "method_capability_map.json")
    out_dir = os.path.join(root, "cache")
    os.makedirs(out_dir, exist_ok=True)

    store = load_json(store_path)
    if store is None:
        print(f"method_store.json not found at {store_path}")
        return 1

    existing_map = load_json(map_path) or {"methods": {}}
    existing_methods = existing_map.get("methods", {})

    rules = build_exact_rules()
    methods = store.get("methods", []) if isinstance(store, dict) else store
    suggestions = {}

    for m in methods:
        if not isinstance(m, dict):
            continue
        cls = normalize_key(m.get("class", ""))
        name = normalize_key(m.get("name", ""))
        if not cls or not name:
            continue
        key = f"{cls}.{name}"
        if key in existing_methods or key.lower() in existing_methods:
            continue
        intent = m.get("intent")
        caps = m.get("capabilities", [])
        if intent or (isinstance(caps, list) and len(caps) > 0):
            continue
        suggestion = suggest_for_method(m, rules)
        if suggestion:
            suggestions[key] = suggestion

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = os.path.join(out_dir, f"method_capability_suggestions_{stamp}.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"generated_at": stamp, "suggestions": suggestions}, f, ensure_ascii=False, indent=2)

    out_md = os.path.join(out_dir, f"method_capability_suggestions_{stamp}.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write("# Method Capability Suggestions\n\n")
        f.write(f"- Generated: {stamp}\n")
        f.write(f"- Suggestions: {len(suggestions)}\n\n")
        for k, v in suggestions.items():
            f.write(f"- `{k}`: intent={v.get('intent')} capabilities={v.get('capabilities')}\n")

    print(f"Wrote: {out_json}")
    print(f"Wrote: {out_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
