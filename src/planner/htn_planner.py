# -*- coding: utf-8 -*-
import json
import os
from typing import List, Dict, Any, Optional
from src.code_synthesis.unified_knowledge_base import UnifiedKnowledgeBase
from src.code_synthesis.type_system import TypeSystem

class HTNPlanner:
    """
    Hierarchical Task Network (HTN) Planner for Code Synthesis.
    
    役割:
    抽象的なゴール（Intent + Entity）を受け取り、それを具体的な
    「メソッド呼び出しの連鎖（Action Sequence）」に分解する。
    
    プロセス:
    1. Goal Decomposition: ゴールをサブタスクに分解 (例: UPDATE -> FETCH + MODIFY + SAVE)
    2. Method Assignment: 各サブタスクに対し、UnifiedKnowledgeBase から最適なメソッドを割り当てる
    3. Contract Validation: メソッド間の型整合性（Data Flow）を確認し、接続できない場合はアダプタ処理を挟む
    """
    
    def __init__(self, ukb: UnifiedKnowledgeBase):
        self.ukb = ukb
        self.type_system = TypeSystem()
        
        # 簡易的な HTN ルール (本来は外部設定ファイル化すべき)
        self.task_networks = {
            "UPDATE": ["FETCH", "MODIFY", "SAVE"],
            "CREATE": ["VALIDATE", "SAVE"],
            "DELETE": ["FETCH", "DELETE"],
            "FETCH": ["FETCH"], # 単純な取得
            "TRANSFORM": ["FETCH", "TRANSFORM", "SAVE"] # ETL的な処理
        }

    def create_action_plan(self, intent: str, target_entity: str, context: Dict[str, Any] = None, source_kind: str = None) -> List[Dict[str, Any]]:
        """
        ゴールに対する具体的なアクションプランを生成する。
        """
        # --- 動的な再帰的分解ロジック ---
        def decompose(task_name, entity, depth=0):
            if depth > 3: return [] # 無限ループ防止
            
            # 1. 直接のマッチングを試行
            query = f"{task_name.lower()} {entity}"
            candidates = self.ukb.search(query, limit=5, intent=task_name, target_entity=entity)
            
            if candidates:
                # 定石パターンはそのまま使用
                if candidates[0].get("origin") == "pattern":
                    return [{"task": task_name, "entity": entity, "method": candidates[0], "status": "assigned"}]
                
                # 単一メソッドが見つかった場合
                return [{"task": task_name, "entity": entity, "method": candidates[0], "status": "assigned"}]
            
            # 2. 定義されたネットワークによる分解
            if task_name in self.task_networks:
                sub_plan = []
                for sub in self.task_networks[task_name]:
                    sub_plan.extend(decompose(sub, entity, depth + 1))
                return sub_plan
            
            # 3. 型ギャップによる動的ブリッジング (例: FETCH -> READ + TRANSFORM)
            if task_name == "FETCH" and depth == 0:
                # ファイル/HTTPから読み込んでオブジェクトに変換する標準的なチェーン
                chain = []
                chain.extend(decompose("READ", entity, depth + 1))
                chain.extend(decompose("JSON_DESERIALIZE", entity, depth + 1))
                return chain

            return [{"task": task_name, "entity": entity, "status": "missing"}]

        plan = decompose(intent, target_entity)
        
        # --- ポストプロセス: 重複排除と役割の集約 ---
        final_plan = []
        covered_indices = set()
        for i, step in enumerate(plan):
            if i in covered_indices: continue
            method = step.get("method")
            if method and method.get('origin') == 'pattern':
                covered_roles = [s.get('role') for s in method.get('steps', [])]
                for j in range(i + 1, len(plan)):
                    if plan[j]["task"] in covered_roles or (plan[j]["task"] == "READ" and "FETCH" in covered_roles):
                        covered_indices.add(j)
            final_plan.append(step)
            
        return final_plan

    def validate_plan(self, plan: List[Dict[str, Any]]) -> List[str]:
        """
        生成されたプランの整合性を検証する。

        各ステップのメソッドの戻り値型が、次のステップのメソッドの第1引数型と
        TypeSystem 上で互換性があるかを確認する。
        互換性があるがアダプタ変換が必要な場合は、各ステップに adapter 情報を付加する。

        Returns:
            検出された型不一致のエラーメッセージのリスト。
            空リストの場合はプラン全体が型整合性を持つ。
        """
        errors = []

        for i, step in enumerate(plan):
            if step["status"] == "missing":
                errors.append(
                    f"Step {i + 1} ({step['task']}): Method missing for entity '{step.get('entity', '?')}'"
                )
                continue

            # 次のステップが存在しない、または次が missing なら型チェックをスキップ
            if i + 1 >= len(plan) or plan[i + 1]["status"] != "assigned":
                continue

            current_method = step.get("method", {})
            next_method = plan[i + 1].get("method", {})

            # 現ステップの戻り値型を取得（"return_type" / "returnType" どちらも許容）
            output_type: str = (
                current_method.get("return_type")
                or current_method.get("returnType")
                or "void"
            )

            # void を出力する場合は次ステップへの型接続が存在しないのでスキップ
            if output_type == "void":
                continue

            # 次ステップの第1引数の型を取得
            next_params: List[Dict] = next_method.get("params", [])
            if not next_params:
                # 引数なしのメソッドは型接続が不要（チェック対象外）
                continue

            input_type: str = next_params[0].get("type", "object")

            # TypeSystem による型互換性チェック（ジェネリクス・継承・ブリッジ変換を包括的に処理）
            is_compat, score, transform = self.type_system.is_compatible(
                target_type=input_type,
                source_type=output_type,
            )

            if is_compat:
                if transform:
                    # 互換性はあるが明示的な変換式（アダプタ）が必要
                    # 次ステップにアダプタ情報を付加して実行時に活用できるようにする
                    plan[i + 1]["adapter"] = {
                        "expression": transform,  # 例: "await {var}.Content.ReadAsStringAsync()"
                        "source_step": i,
                        "source_type": output_type,
                        "target_type": input_type,
                    }
            else:
                error_msg = (
                    f"Step {i + 1}→{i + 2} type mismatch: "
                    f"'{current_method.get('name', '?')}' outputs '{output_type}' "
                    f"but '{next_method.get('name', '?')}' expects '{input_type}'"
                )
                errors.append(error_msg)
                # エラー情報もステップへ付加し、呼び出し側で参照できるようにする
                plan[i + 1]["type_error"] = {
                    "message": error_msg,
                    "source_type": output_type,
                    "expected_type": input_type,
                }

        return errors
