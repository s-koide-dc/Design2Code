# -*- coding: utf-8 -*-
import json
import os
import ast
from typing import List, Dict, Any

class KnowledgeExtractor:
    """
    [Phase 7.1: KnowledgeExtractor (Robust AST version)]
    ソースコードを AST 解析し、型階層、インテント、テンプレート等の
    暗黙的知識を構造的に抽出する。
    """
    def __init__(self, workspace_root: str):
        self.workspace_root = workspace_root
        self.knowledge = {"templates": [], "type_mappings": {}, "common_patterns": {}}

    def extract_from_source(self):
        self._extract_type_system_ast()
        self._extract_ir_patterns_ast()

    def _extract_type_system_ast(self):
        ts_path = os.path.join(self.workspace_root, "src", "code_synthesis", "type_system.py")
        if not os.path.exists(ts_path): return

        try:
            with open(ts_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        # Extract hierarchy
                        if isinstance(target, ast.Attribute) and target.attr == "hierarchy":
                            if isinstance(node.value, ast.Dict):
                                self.knowledge["type_mappings"] = self._parse_ast_dict(node.value)
        except Exception as e:
            print(f"[!] AST error in TypeSystem: {e}")

    def _extract_ir_patterns_ast(self):
        ir_path = os.path.join(self.workspace_root, "src", "ir_generator", "ir_generator.py")
        if not os.path.exists(ir_path): return

        try:
            with open(ir_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())

            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Attribute) and target.attr == "intent_semantic_clusters":
                            if isinstance(node.value, ast.Dict):
                                self.knowledge["common_patterns"] = self._parse_ast_dict(node.value)
        except Exception as e:
            print(f"[!] AST error in IRGenerator: {e}")

    def _parse_ast_dict(self, node: ast.Dict) -> Dict[str, Any]:
        result = {}
        for k, v in zip(node.keys, node.values):
            key = self._get_value(k)
            val = self._get_value(v)
            if key is not None:
                result[key] = val
        return result

    def _get_value(self, node):
        if isinstance(node, ast.Constant): return node.value
        if hasattr(ast, 'Str') and isinstance(node, ast.Str): return node.s # Legacy
        if isinstance(node, ast.List): return [self._get_value(e) for e in node.elts]
        if isinstance(node, ast.Set): 
            res = {self._get_value(e) for e in node.elts}
            return list(res) if isinstance(res, set) else res # JSON serializable
        if isinstance(node, ast.Dict): return self._parse_ast_dict(node)
        return None

    def save_canonical_knowledge(self, output_path: str = None):
        if output_path is None:
            output_path = os.path.join(self.workspace_root, "resources", "canonical_knowledge.json")
        
        existing = {"templates": [], "type_mappings": {}, "common_patterns": {}}
        if os.path.exists(output_path):
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception: pass
        
        # Overwrite structural knowledge
        if self.knowledge["type_mappings"]:
            existing["type_mappings"] = self.knowledge["type_mappings"]
        if self.knowledge["common_patterns"]:
            existing["common_patterns"] = self.knowledge["common_patterns"]
        
        # Templates are managed manually for now or appended if new
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=4, ensure_ascii=False)
        print(f"[+] Canonical knowledge updated with structural data at {output_path}")

if __name__ == "__main__":
    extractor = KnowledgeExtractor(os.getcwd())
    extractor.extract_from_source()
    extractor.save_canonical_knowledge()
