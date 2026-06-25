# -*- coding: utf-8 -*-
import json
import os
from copy import deepcopy
from typing import Any, Dict, Optional


_DEFAULT_POLICY = {
    "semantic_roles": ["FETCH", "PERSIST", "DISPLAY", "TRANSFORM", "HTTP_REQUEST", "LINQ", "EXISTS"],
    "allowed_capabilities": [
        "FETCH",
        "PERSIST",
        "DISPLAY",
        "TRANSFORM",
        "HTTP_REQUEST",
        "LINQ",
        "EXISTS",
        "FILE_IO",
        "READ",
        "WRITE",
        "DATA_FETCH",
        "JSON_DESERIALIZE",
        "JSON_SERIALIZE",
        "HTTP_CONTROL",
    ],
    "pruning": {
        "method_names": {},
        "class_suffixes": {},
        "class_contains": {},
        "class_prefixes": {},
        "exact_classes": {},
        "method_allowlist_by_class": {},
        "header_value_suffixes": [],
        "header_value_methods": [],
    },
}


class MethodStorePolicy:
    """Normalize and gate method-store entries from all harvest sources."""

    def __init__(self, workspace_root: Optional[str] = None, capability_map: Optional[Dict[str, Any]] = None):
        self.workspace_root = workspace_root or os.getcwd()
        self.capability_map = capability_map if capability_map is not None else self._load_capability_map()
        self.policy = self._load_policy()
        self.semantic_roles = set(self.policy.get("semantic_roles", []))
        self.allowed_capabilities = set(self.policy.get("allowed_capabilities", []))
        self.audit = {"accepted": 0, "pruned": 0, "prune_reasons": {}}

    def normalize(self, method_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(method_data, dict):
            self._record_pruned("invalid_payload")
            return None
        method = deepcopy(method_data)
        name = str(method.get("name") or "").strip()
        class_name = str(method.get("class") or "").strip()
        if not name or not class_name:
            self._record_pruned("missing_name_or_class")
            return None
        method["name"] = name
        method["class"] = class_name
        method.setdefault("id", self._default_id(class_name, name))
        method.setdefault("params", [])
        if not isinstance(method["params"], list):
            method["params"] = []
        self._apply_capability_map(method)
        self._normalize_types_and_params(method)
        method["definition"] = self._build_definition(method)
        method["has_side_effects"] = self._infer_side_effects(method)
        method["usings"] = self._normalize_usings(method)
        method["role"] = self._infer_role(method)
        method["origin"] = self._infer_origin(method)
        method["capabilities"] = self._infer_capabilities(method)
        method["summary"] = self._build_summary(method)
        method["tags"] = self._normalize_tags(method)
        prune_reason = self.prune_reason(method)
        if prune_reason:
            self._record_pruned(prune_reason)
            return None
        self.audit["accepted"] += 1
        return method

    def should_prune(self, method: Dict[str, Any]) -> bool:
        return self.prune_reason(method) is not None

    def prune_reason(self, method: Dict[str, Any]) -> Optional[str]:
        if str(method.get("id") or "").startswith("sys."):
            return None
        if self._has_explicit_map(method):
            return None
        name = method.get("name", "")
        class_name = method.get("class", "")
        pruning = self.policy.get("pruning", {})
        for reason, names in self._policy_groups("method_names").items():
            if name in names:
                return reason
        for reason, suffixes in self._policy_groups("class_suffixes").items():
            if any(class_name.endswith(suffix) for suffix in suffixes):
                return reason
        for reason, fragments in self._policy_groups("class_contains").items():
            if any(fragment in class_name for fragment in fragments):
                return reason
        for reason, prefixes in self._policy_groups("class_prefixes").items():
            if reason != "http_header_value" and any(class_name.startswith(prefix) for prefix in prefixes):
                return reason
        for reason, class_names in self._policy_groups("exact_classes").items():
            if class_name in class_names:
                return reason
        if self._is_parse_only_header_value(method):
            return "http_header_value_parser"
        allowlist_by_class = pruning.get("method_allowlist_by_class", {})
        if class_name in allowlist_by_class and name not in set(allowlist_by_class[class_name]):
            return f"{class_name}.not_allowlisted"
        return None

    def get_audit_summary(self) -> Dict[str, Any]:
        return deepcopy(self.audit)

    def reset_audit(self) -> None:
        self.audit = {"accepted": 0, "pruned": 0, "prune_reasons": {}}

    def _load_capability_map(self) -> Dict[str, Any]:
        path = os.path.join(self.workspace_root, "resources", "method_capability_map.json")
        if not os.path.exists(path):
            path = os.path.join(os.getcwd(), "resources", "method_capability_map.json")
        if not os.path.exists(path):
            return {"methods": {}}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_methods = data.get("methods", {}) if isinstance(data, dict) else {}
            methods = {}
            for key, value in raw_methods.items():
                if not isinstance(key, str) or not isinstance(value, dict):
                    continue
                normalized = key.strip()
                if normalized:
                    methods[normalized] = value
                    methods[normalized.lower()] = value
            return {"methods": methods}
        except Exception:
            return {"methods": {}}

    def _load_policy(self) -> Dict[str, Any]:
        path = os.path.join(self.workspace_root, "resources", "method_store_policy.json")
        if not os.path.exists(path):
            path = os.path.join(os.getcwd(), "resources", "method_store_policy.json")
        data = deepcopy(_DEFAULT_POLICY)
        if not os.path.exists(path):
            return data
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        except Exception:
            return data
        if not isinstance(loaded, dict):
            return data
        for key in ("semantic_roles", "allowed_capabilities"):
            if isinstance(loaded.get(key), list):
                data[key] = [str(item) for item in loaded[key] if str(item).strip()]
        if isinstance(loaded.get("pruning"), dict):
            pruning = data["pruning"]
            for key, value in loaded["pruning"].items():
                if key in pruning:
                    pruning[key] = value
        return data

    def _policy_groups(self, key: str) -> Dict[str, set[str]]:
        groups = self.policy.get("pruning", {}).get(key, {})
        if not isinstance(groups, dict):
            return {}
        result = {}
        for reason, values in groups.items():
            if isinstance(reason, str) and isinstance(values, list):
                result[reason] = {str(value) for value in values if str(value).strip()}
        return result

    def _record_pruned(self, reason: str) -> None:
        self.audit["pruned"] += 1
        reasons = self.audit["prune_reasons"]
        reasons[reason] = reasons.get(reason, 0) + 1

    def _lookup_map(self, method: Dict[str, Any]) -> Dict[str, Any]:
        full = f"{method.get('class')}.{method.get('name')}"
        entry = self.capability_map.get("methods", {}).get(full)
        if not isinstance(entry, dict):
            entry = self.capability_map.get("methods", {}).get(full.lower())
        return entry if isinstance(entry, dict) else {}

    def _has_explicit_map(self, method: Dict[str, Any]) -> bool:
        return bool(self._lookup_map(method))

    def _apply_capability_map(self, method: Dict[str, Any]) -> None:
        mapped = self._lookup_map(method)
        if not mapped:
            return
        if isinstance(mapped.get("intent"), str) and mapped["intent"].strip():
            method["intent"] = mapped["intent"].strip()
            method["role"] = method.get("role") or mapped["intent"].strip()
        if isinstance(mapped.get("capabilities"), list):
            method["capabilities"] = [str(c) for c in mapped["capabilities"] if str(c).strip()]
        param_roles = mapped.get("param_roles")
        if isinstance(param_roles, dict):
            for param in method.get("params", []):
                if isinstance(param, dict) and param.get("name") in param_roles:
                    param["role"] = param_roles[param["name"]]

    def _normalize_types_and_params(self, method: Dict[str, Any]) -> None:
        method["return_type"] = self._normalize_type(method.get("return_type") or self._return_type_from_definition(method) or "void")
        for param in method.get("params", []):
            if not isinstance(param, dict):
                continue
            param["name"] = str(param.get("name") or "arg").strip() or "arg"
            param["type"] = self._normalize_type(param.get("type") or "object")
            param["role"] = self._infer_param_role(param)

    def _normalize_type(self, value: Any) -> str:
        text = str(value or "").strip() or "object"
        replacements = {
            "Void": "void",
            "Boolean": "bool",
            "String": "string",
            "Object": "object",
            "Int32": "int",
            "Int64": "long",
            "Double": "double",
            "Single": "float",
            "Decimal": "decimal",
            "Char": "char",
            "Byte": "byte",
        }
        for source, target in replacements.items():
            text = text.replace(f"System.{source}", target)
            if text == source:
                text = target
        return text

    def _return_type_from_definition(self, method: Dict[str, Any]) -> Optional[str]:
        definition = method.get("definition")
        if not isinstance(definition, str) or "(" not in definition:
            return None
        head = definition.split("(", 1)[0].strip()
        parts = head.split()
        if len(parts) < 2:
            return None
        return parts[-2]

    def _infer_param_role(self, param: Dict[str, Any]) -> str:
        role = param.get("role")
        if isinstance(role, str) and role.strip():
            return role.strip()
        name = str(param.get("name") or "")
        exact = {
            "path": "path",
            "fileName": "path",
            "sourceFileName": "path",
            "destFileName": "path",
            "requestUri": "url",
            "url": "url",
            "uri": "url",
            "sql": "sql",
            "query": "sql",
            "source": "source",
            "target": "target",
            "client": "target",
            "cnn": "target",
            "value": "content",
            "values": "content",
            "content": "content",
            "contents": "content",
            "json": "content",
            "text": "content",
            "format": "format",
            "args": "args",
            "predicate": "predicate",
            "selector": "selector",
            "action": "action",
            "callback": "action",
        }
        if name in exact:
            return exact[name]
        type_name = str(param.get("type") or "")
        if "Func<" in type_name or "Action<" in type_name or "Predicate<" in type_name:
            return "action"
        return "param"

    def _build_definition(self, method: Dict[str, Any]) -> str:
        definition = method.get("definition")
        if isinstance(definition, str) and definition.strip():
            return definition.strip()
        params = ", ".join(f"{p.get('type', 'object')} {p.get('name', 'arg')}" for p in method.get("params", []) if isinstance(p, dict))
        return f"{method.get('return_type', 'void')} {method.get('name')}({params})"

    def _infer_side_effects(self, method: Dict[str, Any]) -> bool:
        if isinstance(method.get("has_side_effects"), bool):
            return method["has_side_effects"]
        name = method.get("name", "")
        class_name = method.get("class", "")
        if class_name in {"System.Linq.Enumerable", "System.Text.Json.JsonSerializer", "System.Environment"}:
            return False
        if name.startswith(("Get", "TryGet", "ReadAs")):
            return False
        if name.startswith(("Write", "Set", "Add", "Remove", "Clear", "Delete", "Send", "Post", "Put", "Patch")):
            return True
        return str(method.get("return_type", "")).lower() == "void"

    def _normalize_usings(self, method: Dict[str, Any]) -> list[str]:
        usings = method.get("usings")
        if isinstance(usings, list):
            cleaned = [str(u).strip() for u in usings if str(u).strip()]
            if cleaned:
                return list(dict.fromkeys(cleaned))
        class_name = method.get("class", "")
        if "." not in class_name:
            return []
        return [class_name.rsplit(".", 1)[0]]

    def _infer_role(self, method: Dict[str, Any]) -> str:
        if isinstance(method.get("intent"), str) and method["intent"].strip():
            return method["intent"].strip()
        role = method.get("role")
        if isinstance(role, str) and role.strip() and role.strip() != "INVOKE":
            return role.strip()
        class_name = method.get("class", "")
        name = method.get("name", "")
        if class_name == "System.Linq.Enumerable":
            return "LINQ"
        if class_name in {"System.Net.Http.HttpClient", "System.Net.Http.HttpMessageInvoker"}:
            return "HTTP_REQUEST"
        if class_name == "System.Console":
            return "FETCH" if name.startswith("Read") else "DISPLAY"
        if class_name.startswith("System.Text.Json."):
            return "TRANSFORM"
        caps = set(method.get("capabilities") or [])
        for candidate in ("PERSIST", "FETCH", "TRANSFORM", "DISPLAY", "EXISTS"):
            if candidate in caps:
                return candidate
        return "INVOKE"

    def _infer_origin(self, method: Dict[str, Any]) -> str:
        origin = method.get("origin")
        if isinstance(origin, str) and origin.strip():
            return origin.strip()
        if str(method.get("id") or "").startswith("sys."):
            return "system"
        return "harvested"

    def _infer_capabilities(self, method: Dict[str, Any]) -> list[str]:
        caps = [str(c) for c in (method.get("capabilities") or []) if str(c).strip()]
        role = method.get("role")
        if role in self.semantic_roles:
            caps.append(role)
        class_name = method.get("class", "")
        name = method.get("name", "")
        if class_name == "System.IO.File":
            caps.append("FILE_IO")
        if class_name in {"System.Net.Http.HttpClient", "System.Net.Http.HttpMessageInvoker"}:
            caps.append("HTTP_REQUEST")
        if class_name == "System.Net.Http.HttpContent":
            caps.append("FETCH")
        if class_name == "System.Linq.Enumerable":
            caps.extend(["LINQ", "TRANSFORM"])
        if class_name.startswith("System.Text.Json."):
            caps.append("TRANSFORM")
        if class_name == "System.Console":
            caps.append("FETCH" if name.startswith("Read") else "DISPLAY")
        if name.startswith("Read"):
            caps.append("READ")
        if name.startswith("Write"):
            caps.append("WRITE")
        if "Serialize" in name:
            caps.append("JSON_SERIALIZE")
        if "Deserialize" in name or name in {"Parse", "ParseAsync"}:
            caps.append("JSON_DESERIALIZE")
        return list(dict.fromkeys(c for c in caps if c in self.allowed_capabilities))

    def _build_summary(self, method: Dict[str, Any]) -> str:
        summary = method.get("summary")
        if isinstance(summary, str) and summary.strip() and "Capabilities:" in summary:
            return summary.strip()
        prefix = "Standard library" if method.get("origin") == "system" else "Harvested"
        caps = method.get("capabilities") or []
        cap_text = f" Capabilities: {', '.join(caps)}." if caps else ""
        return f"{prefix} method: {method.get('name')} in {method.get('class')}.{cap_text}"

    def _normalize_tags(self, method: Dict[str, Any]) -> list[str]:
        tags = [str(t) for t in (method.get("tags") or []) if str(t).strip()]
        tags.extend(method.get("capabilities") or [])
        if method.get("role"):
            tags.append(method["role"])
        return list(dict.fromkeys(tags))

    def _is_parse_only_header_value(self, method: Dict[str, Any]) -> bool:
        class_name = method.get("class", "")
        pruning = self.policy.get("pruning", {})
        prefixes = self._policy_groups("class_prefixes").get("http_header_value", set())
        if not any(class_name.startswith(prefix) for prefix in prefixes):
            return False
        suffix = class_name.rsplit(".", 1)[-1]
        suffixes = {str(s) for s in pruning.get("header_value_suffixes", [])}
        methods = {str(m) for m in pruning.get("header_value_methods", [])}
        return suffix in suffixes and method.get("name") in methods

    def _default_id(self, class_name: str, name: str) -> str:
        return f"{class_name}.{name}".lower()
