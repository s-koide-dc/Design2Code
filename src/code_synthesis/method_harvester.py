# -*- coding: utf-8 -*-
import json
import os
import hashlib
from typing import Dict, List, Any, Optional

class MethodHarvester:
    """既存コードからメソッドを自動収集してストアを更新するクラス"""

    def __init__(self, config_manager, morph_analyzer=None):
        self.config_manager = config_manager
        self.store_path = os.path.join(os.getcwd(), 'resources', 'method_store.json')
        self.capability_map = self._load_capability_map()
        from src.utils.nuget_client import NuGetClient
        self.nuget_client = NuGetClient(config_manager)

    def harvest_from_analysis(self, analysis_output_path: str):
        """Roslynの解析結果ディレクトリからメソッドを抽出する"""
        manifest_path = os.path.join(analysis_output_path, "manifest.json")
        if not os.path.exists(manifest_path):
            return {"status": "error", "message": "Manifest not found"}

        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        new_methods = []
        details_dir = os.path.join(analysis_output_path, "details")
        
        for obj in manifest.get("objects", []):
            if obj.get("type") not in ["Class", "Record", "Struct"]:
                continue
            
            detail_file = os.path.join(details_dir, f"{obj['id']}.json")
            if not os.path.exists(detail_file):
                continue
                
            with open(detail_file, 'r', encoding='utf-8') as f:
                detail = json.load(f)
            
            for m in detail.get("methods", []):
                # フィルタリング基準
                cc = m.get("metrics", {}).get("cyclomaticComplexity", 0)
                if cc > 5 or cc == 0: continue # 複雑すぎる、または空のメソッドは除外
                if m.get("accessibility") != "Public": continue # 公開メソッドのみ
                
                # 部品化
                method_entry = self._create_method_entry(m, detail.get("fullName"), detail.get("usings", []))
                new_methods.append(method_entry)

        from .method_store import MethodStore
        store = MethodStore(config=self.config_manager)
        for nm in new_methods:
            store.add_method(nm, overwrite=True)
            
        return {"status": "success", "count": len(new_methods)}

    def _create_method_entry(self, m_detail: Dict[str, Any], class_full_name: str, usings: List[str] = None) -> Dict[Any, Any]:
        """Roslynのメソッド詳細データをストア形式に変換"""
        params = []
        for p in m_detail.get("parameters", []):
            role = self._extract_param_role(p, class_full_name, m_detail.get("name"))
            params.append({"name": p.get("name"), "type": p.get("type"), "role": role})

        capabilities = self._extract_capabilities(m_detail, class_full_name)
        intent = self._extract_intent(m_detail, class_full_name)
        has_side_effects = self._detect_side_effects(m_detail.get("bodyCode", ""), m_detail.get("name", ""))

        is_static = "static" in m_detail.get("modifiers", [])
        prefix = "" if is_static else "_service."
        
        call_params = ", ".join([f"{{{p['name']}}}" for p in params])
        code_template = f"{prefix}{m_detail['name']}({call_params})"

        namespace = class_full_name.rsplit(".", 1)[0] if "." in class_full_name else ""
        raw_code = m_detail.get("bodyCode", "")
        code_body = raw_code
        
        if namespace and raw_code:
            # Keep the full body unless an explicit extraction is provided upstream.
            code_body = raw_code

        dependencies = set(); usings_list = usings or []
        for u in usings_list:
            if u not in ["System", "System.Linq"]:
                pkg_info = self.nuget_client.resolve_package(u)
                if pkg_info: dependencies.add(pkg_info["name"])

        tags = []
        if capabilities:
            tags.extend(capabilities)
        if intent:
            tags.append(intent)
        if has_side_effects:
            tags.append("side-effect")

        return {
            "id": hashlib.md5(f"{class_full_name}.{m_detail['name']}".encode()).hexdigest()[:8],
            "name": m_detail["name"],
            "class": class_full_name,
            "return_type": m_detail.get("returnType", "void").replace("Task<", "").replace(">", ""),
            "params": params,
            "capabilities": capabilities,
            "intent": intent,
            "code": code_template,
            "definition": m_detail.get("bodyCode", ""),
            "namespace": namespace,
            "usings": usings_list,
            "dependencies": list(dependencies),
            "tags": list(set(tags + capabilities)),
            "has_side_effects": has_side_effects,
            "tier": 1 if (class_full_name.startswith("System.") or class_full_name.startswith("Common.")) else 2
        }

    def _extract_intent(self, m_detail: Dict[str, Any], class_full_name: str) -> Optional[str]:
        if isinstance(m_detail.get("intent"), str) and m_detail["intent"].strip():
            return m_detail["intent"].strip()
        attrs = self._extract_attributes(m_detail)
        intent = self._get_attr_single(attrs, ["Intent", "IntentAttribute"])
        if intent:
            return intent
        mapped = self._lookup_map_value(class_full_name, m_detail.get("name"), "intent")
        return mapped if isinstance(mapped, str) else None

    def _extract_capabilities(self, m_detail: Dict[str, Any], class_full_name: str) -> List[str]:
        if isinstance(m_detail.get("capabilities"), list):
            return [str(c) for c in m_detail.get("capabilities", []) if str(c).strip()]
        attrs = self._extract_attributes(m_detail)
        caps = self._get_attr_list(attrs, ["Capabilities", "CapabilitiesAttribute"])
        if caps:
            return caps
        mapped = self._lookup_map_value(class_full_name, m_detail.get("name"), "capabilities")
        return mapped if isinstance(mapped, list) else []

    def _extract_param_role(self, p_detail: Dict[str, Any], class_full_name: str, method_name: Optional[str]) -> Optional[str]:
        if isinstance(p_detail.get("role"), str) and p_detail["role"].strip():
            return p_detail["role"].strip()
        attrs = self._extract_attributes(p_detail)
        role = self._get_attr_single(attrs, ["ParamRole", "ParamRoleAttribute", "Role", "RoleAttribute"])
        if role:
            return role
        mapped = self._lookup_param_role(class_full_name, method_name, p_detail.get("name"))
        return mapped if isinstance(mapped, str) else None

    def _extract_attributes(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw = payload.get("attributes")
        if isinstance(raw, list):
            return [a for a in raw if isinstance(a, dict)]
        return []

    def _get_attr_single(self, attrs: List[Dict[str, Any]], names: List[str]) -> Optional[str]:
        for attr in attrs:
            name = str(attr.get("name") or attr.get("attribute") or "")
            if not name:
                continue
            if self._attr_name_matches(name, names):
                value = attr.get("value")
                if isinstance(value, str) and value.strip():
                    return value.strip()
                args = attr.get("args")
                if isinstance(args, list) and args:
                    if isinstance(args[0], str) and args[0].strip():
                        return args[0].strip()
        return None

    def _get_attr_list(self, attrs: List[Dict[str, Any]], names: List[str]) -> List[str]:
        results: List[str] = []
        for attr in attrs:
            name = str(attr.get("name") or attr.get("attribute") or "")
            if not name:
                continue
            if not self._attr_name_matches(name, names):
                continue
            value = attr.get("value")
            if isinstance(value, list):
                results.extend([str(v) for v in value if str(v).strip()])
            args = attr.get("args")
            if isinstance(args, list):
                results.extend([str(v) for v in args if str(v).strip()])
            elif isinstance(args, str) and args.strip():
                results.append(args.strip())
        return list(dict.fromkeys(results))

    def _attr_name_matches(self, name: str, candidates: List[str]) -> bool:
        n = name.strip()
        n_short = n[:-9] if n.endswith("Attribute") else n
        for cand in candidates:
            c = cand.strip()
            c_short = c[:-9] if c.endswith("Attribute") else c
            if n == c or n_short == c or n == c_short:
                return True
        return False

    def _load_capability_map(self) -> Dict[str, Any]:
        path = os.path.join(os.getcwd(), "resources", "method_capability_map.json")
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            methods = data.get("methods", {}) if isinstance(data, dict) else {}
            normalized = {}
            for k, v in methods.items():
                if not isinstance(k, str):
                    continue
                key = k.strip()
                if not key:
                    continue
                normalized[key] = v
                normalized[key.lower()] = v
            return {"methods": normalized}
        except Exception:
            return {}

    def _lookup_map_value(self, class_full_name: str, method_name: Optional[str], key: str) -> Any:
        if not self.capability_map:
            return None
        if not class_full_name or not method_name:
            return None
        full = f"{class_full_name}.{method_name}"
        methods = self.capability_map.get("methods", {})
        entry = methods.get(full) or methods.get(full.lower())
        if not isinstance(entry, dict):
            return None
        return entry.get(key)

    def _lookup_param_role(self, class_full_name: str, method_name: Optional[str], param_name: Optional[str]) -> Optional[str]:
        if not class_full_name or not method_name or not param_name:
            return None
        entry = self._lookup_map_value(class_full_name, method_name, "param_roles")
        if not isinstance(entry, dict):
            return None
        return entry.get(param_name)

    def _detect_side_effects(self, body_code: str, method_name: str) -> bool:
        name_lower = (method_name or "").lower()
        code = body_code or ""
        # Conservative detection of destructive or mutating operations
        destructive_tokens = [
            "File.Delete", "Directory.Delete", "DELETE FROM", "DROP ", "TRUNCATE ", "Remove(", "RemoveRange(", "Delete("
        ]
        if any(tok in code for tok in destructive_tokens):
            return True
        if any(k in name_lower for k in ["delete", "remove", "drop", "truncate"]):
            return True
        return False

    def _update_store(self, new_methods: List[Dict[Any, Any]]):
        """Deprecated: Use MethodStore.add_method directly."""
        pass
