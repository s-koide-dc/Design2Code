# -*- coding: utf-8 -*-
from typing import Dict, List, Optional, Set, Tuple

class TypeSystem:
    """
    C# の型システム（継承関係、ジェネリクス互換性）をシミュレートするクラス。
    指示文の文脈と構造から、最適な型を論理的に導出する。
    """
    def __init__(self):
        self.hierarchy: Dict[str, Set[str]] = {
            "List<T>": {"IEnumerable<T>", "ICollection<T>", "IList<T>", "IEnumerable", "object"},
            "string": {"object", "IComparable", "ICloneable"},
            "int": {"object", "ValueType"},
            "decimal": {"object", "ValueType"},
            "bool": {"object", "ValueType"},
            "HttpResponseMessage": {"object", "IDisposable"},
            "HttpContent": {"object", "IDisposable"},
            "Task<T>": {"object", "Task"},
            "SqlConnection": {"IDbConnection", "DbConnection", "object"},
            "SqliteConnection": {"IDbConnection", "DbConnection", "object"},
            "IDbConnection": {"IDisposable", "object"},
            "HttpClient": {"IDisposable", "object"}
        }
        self.aliases = {"String": "string", "Int32": "int", "Boolean": "bool", "Void": "void"}
        self.reserved_system_types = {
            "Task", "List", "IEnumerable", "ICollection", "IList", "IQueryable", 
            "Dictionary", "IDictionary", "HashSet", "ActionResult", "IActionResult", 
            "Response", "Request", "Data", "Repo", "Context", "Connection", "String", "Int32"
        }
        self.bridges = {
            "HttpResponseMessage": {"string": "await {var}.Content.ReadAsStringAsync()", "HttpContent": "{var}.Content"},
            "decimal": {"string": "{var}.ToString()"},
            "int": {"string": "{var}.ToString()"},
            "bool": {"string": "{var}.ToString()"},
            "object": {"string": "{var}?.ToString()"}
        }

    def is_system_type(self, type_name: str) -> bool:
        base = type_name.split('<')[0].split('.')[-1]
        return base in self.reserved_system_types or base.lower() in self.aliases.values()

    def normalize_type(self, type_name: str) -> str:
        if not type_name: return "void"
        type_name = str(type_name)
        if "`" in type_name:
            parts = type_name.split("`", 1)
            left = parts[0]
            right = parts[1] if len(parts) > 1 else ""
            digits = ""
            for ch in right:
                if ch.isdigit():
                    digits += ch
                else:
                    break
            if digits == "1":
                type_name = f"{left}<T>"
            elif digits == "2":
                type_name = f"{left}<T1,T2>"
        lt = type_name.find("<")
        base = type_name if lt == -1 else type_name[:lt]
        gen = "" if lt == -1 else type_name[lt:]
        base = base.split(".")[-1]
        base = self.aliases.get(base, base)
        return f"{base}{gen}"

    def unwrap_task_type(self, type_name: Optional[str]) -> Optional[str]:
        if not type_name:
            return type_name
        t = self.normalize_type(str(type_name).strip())
        if t.startswith("Task<") and t.endswith(">") and len(t) > len("Task<>"):
            return t[len("Task<"):-1].strip()
        return t

    def extract_generic_inner(self, type_hint: Optional[str]) -> Optional[str]:
        if not type_hint:
            return None
        t = self.normalize_type(str(type_hint).strip())
        if t.endswith("[]") and len(t) > 2:
            return t[:-2].strip()
        start = t.find("<")
        end = t.rfind(">")
        if start == -1 or end == -1 or end <= start + 1:
            return None
        return t[start + 1:end].strip()

    def is_compatible(self, target_type: str, source_type: str, context_text: str = "", intent: str = None) -> Tuple[bool, int, Optional[str]]:
        target = self.normalize_type(target_type)
        source = self.normalize_type(source_type)
        if target == source: return True, 100, None
        
        # 0. Generic Wildcard Handling
        if "<T>" in target or "T" == target:
            t_base = target.split('<')[0]
            s_base = source.split('<')[0]
            if t_base == s_base or (t_base in ["IEnumerable", "IQueryable", "List"] and s_base in ["IEnumerable", "IQueryable", "List"]):
                return True, 95, None
        
        # 1. Bridge Conversion
        for s_base, targets in self.bridges.items():
            if s_base in source and target in targets:
                return True, 90, targets[target]
        
        # 2. Inheritance
        source_base = source.split('<')[0]
        if source_base in self.hierarchy:
            if target in self.hierarchy[source_base] or any(target.startswith(p.split('<')[0]) for p in self.hierarchy[source_base]):
                return True, 80, None
        
        # 3. Numeric & Object Fallback
        if target == "object": return True, 10, None
        if target == "string" and source in ["int", "decimal", "bool", "double", "float", "long"]:
            return True, 1, "{var}.ToString()"
        if target == "long" and source == "int":
            return True, 90, None
        
        return False, 0, None

    def concretize_generic(self, generic_type: str, context_text: str, mandatory_hint: str = None, cardinality: str = None) -> str:
        t = self.normalize_type(generic_type)
        if "<T>" not in t and t not in ["T", "TSource", "TResult"]: return t

        # Use mandatory hint if provided and not just a placeholder
        entity = mandatory_hint
        if entity:
            if "<" in entity and ">" in entity:
                start = entity.find("<")
                end = entity.rfind(">")
                if 0 <= start < end:
                    entity = entity[start + 1:end].strip()
            if entity in ["Item", "T", "object"]: entity = None

        if not entity:
            # Fallback to context analysis
            tokens = []
            current = []
            for ch in str(context_text):
                if ch.isalnum() or ch == "_":
                    current.append(ch)
                else:
                    if current:
                        tokens.append("".join(current))
                        current = []
            if current:
                tokens.append("".join(current))
            for m in reversed(tokens):
                if not m:
                    continue
                if not m[0].isupper():
                    continue
                if self.is_system_type(m):
                    continue
                if m in ["Inventory", "Db", "Database"]:
                    continue
                entity = m
                break
            
        if not entity: entity = "Item"

        # 27.115: Use cardinality as primary signal for collection wrapping
        is_collection = (cardinality == "COLLECTION")
        has_collection_wrapper = any(k in t for k in ["IEnumerable", "List", "[]", "ICollection", "IList"])
        
        concrete_t = entity
        if is_collection and not has_collection_wrapper:
            concrete_t = f"List<{entity}>"

        res = t.replace("<T>", f"<{concrete_t}>").replace("<TSource>", f"<{concrete_t}>").replace("<TResult>", f"<{concrete_t}>") if "<" in t else (concrete_t if t in ["T", "TSource", "TResult"] else t)
        
        if "List<List<" in res: res = res.replace("List<List<", "List<")
        return res
