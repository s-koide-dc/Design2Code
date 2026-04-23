# -*- coding: utf-8 -*-
from typing import List, Dict, Any, Optional

class IRPatcher:
    """ReplanHint に基づいて IR ツリーを修正するクラス"""

    def apply_patches(self, ir_tree: Dict[str, Any], hints: List[Dict[str, Any]]) -> Dict[str, Any]:
        patched_ir = ir_tree # In-place for simplicity or deepcopy
        
        for hint in hints:
            patch = hint.get("patch", {})
            p_type = patch.get("type")
            
            if p_type == "FORCE_INTENT_RESOLUTION":
                self._patch_intent(patched_ir, patch)
            elif p_type == "REBIND_INPUT_LINK":
                self._patch_links(patched_ir, patch)
            elif p_type == "ADD_POCO_PROPERTY":
                self._patch_entities(patched_ir, patch)
            elif p_type == "ENSURE_FIELD_OR_LOCAL":
                self._patch_required_fields(patched_ir, patch)
            elif p_type == "FORCE_VARIABLE_BINDING":
                self._patch_node_semantic(patched_ir, patch["node_id"], {"binding_priority": "variable"})
            elif p_type == "FIX_LOGIC_GAPS":
                for node_id in patch.get("failed_texts", []):
                    self._patch_node_semantic(patched_ir, node_id, {"retry_logic": True})
                    if patch.get("upstream_vars"):
                        self._patch_node_semantic_roles(
                            patched_ir,
                            node_id,
                            {"preferred_vars": patch.get("upstream_vars")}
                        )
                    if patch.get("recommend_var"):
                        self._patch_node_semantic_roles(
                            patched_ir,
                            node_id,
                            {"preferred_vars": [patch.get("recommend_var")]}
                        )
                    if patch.get("drop_at"):
                        target_node = self._find_node(patched_ir.get("logic_tree", []), node_id)
                        if target_node and isinstance(patch.get("drop_at"), str):
                            if self._is_upstream_node(patched_ir.get("logic_tree", []), patch.get("drop_at"), node_id):
                                target_node["input_link"] = patch.get("drop_at")
                
        return patched_ir

    def _patch_node_semantic(self, ir: Dict[str, Any], node_id: str, updates: Dict[str, Any]):
        node = self._find_node(ir.get("logic_tree", []), node_id)
        if node:
            node.setdefault("semantic_map", {}).update(updates)

    def _patch_node_semantic_roles(self, ir: Dict[str, Any], node_id: str, updates: Dict[str, Any]):
        node = self._find_node(ir.get("logic_tree", []), node_id)
        if node:
            semantic_map = node.setdefault("semantic_map", {})
            roles = semantic_map.setdefault("semantic_roles", {})
            for k, v in updates.items():
                if v is not None:
                    roles[k] = v

    def _patch_required_fields(self, ir: Dict[str, Any], patch: Dict[str, Any]):
        symbol = patch.get("name")
        if not symbol: return
        
        # シンボル（型名など）からフィールド名への論理マッピング
        # これにより、CS0103 "HttpClient" エラーを "_httpClient" フィールドの不足と解釈する。
        norm_map = {
            "HttpClient": "_httpClient",
            "IDbConnection": "_dbConnection",
            "SqlConnection": "_dbConnection",
            "SqliteConnection": "_dbConnection"
        }
        field_name = norm_map.get(symbol, symbol)
        
        if "required_fields" not in ir:
            ir["required_fields"] = []
        
        if field_name not in ir["required_fields"]:
            ir["required_fields"].append(field_name)

    def _find_node(self, nodes: List[Dict[str, Any]], target_id: str) -> Optional[Dict[str, Any]]:
        for node in nodes:
            if node.get("id") == target_id:
                return node
            # 再帰的に検索
            for child_key in ["children", "else_children"]:
                if child_key in node and isinstance(node[child_key], list):
                    found = self._find_node(node[child_key], target_id)
                    if found:
                        return found
        return None

    def _collect_node_order(self, nodes: List[Dict[str, Any]]) -> List[str]:
        order: List[str] = []
        for node in nodes:
            node_id = node.get("id")
            if isinstance(node_id, str):
                order.append(node_id)
            for child_key in ["children", "else_children"]:
                if child_key in node and isinstance(node[child_key], list):
                    order.extend(self._collect_node_order(node[child_key]))
        return order

    def _is_upstream_node(self, nodes: List[Dict[str, Any]], source_id: str, target_id: str) -> bool:
        order = self._collect_node_order(nodes)
        if source_id not in order or target_id not in order:
            return False
        return order.index(source_id) < order.index(target_id)

    def _patch_intent(self, ir: Dict[str, Any], patch: Dict[str, Any]):
        target_id = patch.get("target_id")
        method = patch.get("method", "")
        
        node = self._find_node(ir.get("logic_tree", []), target_id)
        if node:
            # SaveChangesAsync 等が含まれる場合は PERSIST に強制
            if "Save" in method or "Update" in method or "Delete" in method:
                node["intent"] = "PERSIST"
            else:
                # デフォルトで何か有用な変更を試みる
                node["intent"] = "ACTION"

    def _patch_links(self, ir: Dict[str, Any], patch: Dict[str, Any]):
        source_id = patch.get("source_id")
        target_id = patch.get("target_id")
        
        target_node = self._find_node(ir.get("logic_tree", []), target_id)
        if target_node:
            if "input_refs" not in target_node:
                target_node["input_refs"] = []
            if source_id and source_id not in target_node["input_refs"]:
                target_node["input_refs"].append(source_id)

    def _patch_entities(self, ir: Dict[str, Any], patch: Dict[str, Any]):
        # エンティティ定義の拡張（現在は ir["poco_defs"] などを想定）
        member = patch.get("member")
        # TODO: 実装が必要な場合に備えてスケルトンを維持
        pass
