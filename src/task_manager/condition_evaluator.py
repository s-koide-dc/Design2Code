# -*- coding: utf-8 -*-
# src/task_manager/condition_evaluator.py

class ConditionEvaluator:
    """タスクの状態遷移条件を評価するクラス"""
    
    @staticmethod
    def evaluate(condition: any, context: dict) -> bool:
        """
        構造化された条件を現在のコンテキストに対して評価します。
        
        Args:
            condition: 文字列（レガシー互換）またはJSON形式の条件辞書。
            context: パイプラインコンテキスト。
            
        Returns:
            bool: 条件が満たされている場合はTrue、それ以外はFalse。
        """
        if isinstance(condition, str):
            if condition.lower() == "true": return True
            if condition.lower() == "false": return False
            return False

        if not isinstance(condition, dict):
            return False

        cond_type = condition.get("type")

        if cond_type == "always_true":
            return True
        
        if cond_type == "entity_exists":
            key = condition.get("key")
            # 1. Check entities extracted in the current turn
            analysis = context.get("analysis", {})
            entities_from_analysis = analysis.get("entities", {})
            entity_from_analysis = entities_from_analysis.get(key)
            
            exists_in_analysis = False
            if isinstance(entity_from_analysis, dict):
                # Ensure it has a non-empty value
                if entity_from_analysis.get("value"): exists_in_analysis = True
            elif isinstance(entity_from_analysis, str):
                if entity_from_analysis.strip(): exists_in_analysis = True
            
            if exists_in_analysis:
                # print(f"[DEBUG] ConditionEvaluator: '{key}' exists in current turn analysis")
                return True
            
            # 2. Check parameters already stored in the active task
            task = context.get("task")
            if not task:
                 # Fallback to session check if task not in context?
                 # But manage_task_state usually puts it there.
                 return False

            task_params = task.get("parameters", {})
            entity_from_params = task_params.get(key)
            
            exists_in_params = False
            if isinstance(entity_from_params, dict):
                if entity_from_params.get("value"): exists_in_params = True
            elif isinstance(entity_from_params, str):
                if entity_from_params.strip(): exists_in_params = True

            if exists_in_params:
                return True
            return False

        if cond_type == "entity_value_is":
            key = condition.get("key")
            value = condition.get("value")
            
            # 現在のターンのエンティティをチェック
            entities_from_analysis = context.get("analysis", {}).get("entities", {})
            entity_from_analysis = entities_from_analysis.get(key)
            if isinstance(entity_from_analysis, dict) and entity_from_analysis.get("value") == value:
                return True
            if isinstance(entity_from_analysis, str) and entity_from_analysis == value:
                return True
            
            # タスクに保存されているパラメータをチェック
            task_params = context.get("task", {}).get("parameters", {})
            entity_from_params = task_params.get(key)
            if isinstance(entity_from_params, dict) and entity_from_params.get("value") == value:
                return True
            if isinstance(entity_from_params, str) and entity_from_params == value:
                return True
            return False

        if cond_type == "intent_is":
            return context.get("analysis", {}).get("intent") == condition.get("intent")

        if cond_type == "all_of":
            predicates = condition.get("predicates", [])
            for pred in predicates:
                if not ConditionEvaluator.evaluate(pred, context):
                    return False
            return True

        if cond_type == "any_of":
            predicates = condition.get("predicates", [])
            for pred in predicates:
                if ConditionEvaluator.evaluate(pred, context):
                    return True
            return False

        return False
        # TODO: Implement Logic: **条件タイプの処理**:
