# -*- coding: utf-8 -*-
import json
import os
from typing import List, Dict, Any

class TemplateRegistry:
    def __init__(self, knowledge_path: str = None):
        self.templates = []
        if knowledge_path is None:
            # Default path relative to project root
            root = os.getcwd()
            knowledge_path = os.path.join(root, "resources", "canonical_knowledge.json")
        
        if os.path.exists(knowledge_path):
            try:
                with open(knowledge_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.templates = data.get("templates", [])
            except Exception as e:
                print(f"[!] Error loading TemplateRegistry: {e}")
        else:
            print(f"[!] TemplateRegistry file not found: {knowledge_path}")

    def get_templates_for_intent(self, intent: str, source_kind: str = None, is_db_allowed: bool = False) -> List[Dict[str, Any]]:
        results = []
        for t in self.templates:
            # 27.280: Hard-filter problematic/legacy templates that interfere with high-fidelity synthesis
            if t.get("name") in ["Enumerable.ToList", "List.Add", "GenericAction"]:
                continue

            # 27.128: Check both primary intent and capabilities
            t_intent = t.get("intent")
            t_caps = t.get("capabilities", [])
            if t_intent != intent and intent not in t_caps:
                continue
            
            # Special filter for DB
            if (intent in ["DATABASE_QUERY", "FETCH", "PERSIST"] or "DATABASE_QUERY" in t_caps) and t.get("target") == "_dbConnection":
                if not is_db_allowed:
                    continue
            
            # Special filter for Source Kind
            t_source = t.get("source_kind")
            if t_source and source_kind and t_source != source_kind:
                continue
            
            results.append(t)
        return results
