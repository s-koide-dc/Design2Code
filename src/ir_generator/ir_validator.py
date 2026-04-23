# -*- coding: utf-8 -*-
import json
import os
from typing import List, Dict, Any, Set

class IRValidator:
    """
    IRツリーの論理的整合性とデータフローを静的に検証するクラス。
    """
    def __init__(self, config_manager, type_system=None):
        from src.code_synthesis.type_system import TypeSystem
        self.config_manager = config_manager
        self.type_system = type_system or TypeSystem()
        
        root = getattr(config_manager, 'workspace_root', getattr(config_manager, 'root_dir', os.getcwd()))
        entity_path = os.path.join(root, "resources", "entity_schema.json")
        self.entity_schema = {}
        if os.path.exists(entity_path):
            with open(entity_path, 'r', encoding='utf-8') as f:
                self.entity_schema = json.load(f)

    def validate(self, ir_tree: Dict[str, Any]) -> Dict[str, Any]:
        errors = []
        warnings = []
        
        # 初期スコープ (Root)
        # 形式: [{"name": str, "type": str, "is_collection": bool}]
        symbol_table = []
        
        self._traverse_and_validate(ir_tree.get("logic_tree", []), symbol_table, errors, warnings)
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }

    def _traverse_and_validate(self, nodes: List[Dict[str, Any]], symbol_table: List[Dict[str, Any]], errors: List[str], warnings: List[str]):
        for node in nodes:
            node_type = node.get("type")
            intent = str(node.get("intent") or "").upper()
            
            if node_type in ["ACTION", "TRANSFORM"]:
                self._validate_action(node, symbol_table, errors, warnings)
                # 仮の出力登録 (本来はメソッドストアの戻り値型を見る必要があるが、ここではエンティティ名から推論)
                target = node.get("target_entity")
                if target and target != "Item":
                    if intent in ["FETCH", "DATABASE_QUERY", "JSON_DESERIALIZE", "HTTP_REQUEST", "FILE_IO", "LINQ", "TRANSFORM"]:
                        is_coll = self._is_collection(node)
                        symbol_table.append({"name": target.lower(), "type": target, "is_collection": is_coll})

            elif node_type == "LOOP":
                # ループ対象がシンボルテーブルにあるか確認
                target = node.get("target_entity")
                found = False
                for sym in symbol_table:
                    if sym["type"] == target and sym["is_collection"]:
                        found = True
                        break
                
                if not found:
                    # 警告レベル（直前のアクションで取得しているはずだが、明示的なリストがない場合）
                    warnings.append(f"LOOP target '{target}' might not be a collection in current scope.")
                
                # ループ内スコープ
                inner_symbol_table = list(symbol_table)
                # ループ変数を追加
                inner_symbol_table.append({"name": "item", "type": target or "Item", "is_collection": False})
                
                children = self._get_children(node)
                if not children:
                    warnings.append(f"Empty LOOP body for {target}")
                else:
                    self._traverse_and_validate(children, inner_symbol_table, errors, warnings)

            elif node_type == "CONDITION":
                children = self._get_children(node)
                else_children = self._get_else_children(node)
                if not children and not else_children:
                    warnings.append("CONDITION block has no body or else_body.")
                
                # If body scope
                if children:
                    self._traverse_and_validate(children, list(symbol_table), errors, warnings)
                # Else body scope
                if else_children:
                    self._traverse_and_validate(else_children, list(symbol_table), errors, warnings)

            elif node_type == "WRAPPER":
                children = self._get_children(node)
                if children:
                    self._traverse_and_validate(children, list(symbol_table), errors, warnings)
                else:
                    warnings.append("WRAPPER (Retry, etc.) has no body.")
            elif node_type in ["ELSE", "END"]:
                continue

    def _validate_action(self, node: Dict[str, Any], symbol_table: List[Dict[str, Any]], errors: List[str], warnings: List[str]):
        target = node.get("target_entity")
        intent = str(node.get("intent") or "").upper()
        
        # 依存関係の欠落チェック (intent ベース)
        if intent in ["PERSIST", "WRITE"]:
            if target and not any(sym["type"] == target for sym in symbol_table):
                errors.append(f"Action '{intent}' requires '{target}' to be defined/loaded, but it's missing in scope.")

    def _get_children(self, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        return node.get("children") or node.get("body") or []

    def _get_else_children(self, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        return node.get("else_children") or node.get("else_body") or []

    def _is_collection(self, node: Dict[str, Any]) -> bool:
        cardinality = str(node.get("cardinality") or "").upper()
        if cardinality == "COLLECTION":
            return True
        output_type = node.get("output_type")
        if not output_type:
            return False
        t = self.type_system.normalize_type(str(output_type))
        if t.endswith("[]"):
            return True
        return any(k in t for k in ["IEnumerable", "ICollection", "IList", "List<"])
