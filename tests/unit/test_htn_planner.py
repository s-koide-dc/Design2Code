# -*- coding: utf-8 -*-
"""
Unit tests for HTNPlanner.validate_plan().

TypeSystem.is_compatible() を活用した型接続検証のテスト。
正規表現・スコアリング・キーワードマッチに依存しない、
型システムによる決定論的な検証を確認する。
"""
import unittest
from unittest.mock import MagicMock
from src.planner.htn_planner import HTNPlanner
from src.code_synthesis.unified_knowledge_base import UnifiedKnowledgeBase
from src.code_synthesis.type_system import TypeSystem


def _make_step(task: str, status: str, return_type: str, method_name: str,
               next_param_type: str = None, entity: str = "Item") -> dict:
    """テスト用プランステップを構築するヘルパー。"""
    params = []
    if next_param_type:
        params = [{"name": "input", "type": next_param_type}]
    return {
        "task": task,
        "entity": entity,
        "status": status,
        "method": {
            "name": method_name,
            "return_type": return_type,
            "params": params,
        },
    }


class TestHTNPlannerValidatePlan(unittest.TestCase):

    def setUp(self):
        """HTNPlannerをモックのUKBで初期化する。"""
        mock_ukb = MagicMock(spec=UnifiedKnowledgeBase)
        self.planner = HTNPlanner(ukb=mock_ukb)
        self.type_system = TypeSystem()

    # ------------------------------------------------------------------
    # Happy Path（正常ケース）
    # ------------------------------------------------------------------

    def test_single_step_plan_has_no_errors(self):
        """1ステップのプランは型接続チェックが不要で、エラーなし。"""
        plan = [_make_step("FETCH", "assigned", "IEnumerable<User>", "GetUsers")]
        errors = self.planner.validate_plan(plan)
        self.assertEqual(errors, [])

    def test_compatible_direct_type_chain(self):
        """
        IEnumerable<User> → IEnumerable<T> の接続は TypeSystem が互換と判定する。
        エラーなし、アダプタも不要。
        """
        plan = [
            _make_step("FETCH",     "assigned", "IEnumerable<User>", "GetUsers"),
            _make_step("TRANSFORM", "assigned", "IEnumerable<User>", "Where",
                       next_param_type="IEnumerable<T>"),
        ]
        errors = self.planner.validate_plan(plan)
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")
        # アダプタ不要のはずなので adapter キーがないこと
        self.assertNotIn("adapter", plan[1])
        self.assertNotIn("type_error", plan[1])

    def test_exact_type_match_is_compatible(self):
        """完全型一致（string → string）はエラーなし。"""
        plan = [
            _make_step("READ",    "assigned", "string", "ReadAllText"),
            _make_step("DISPLAY", "assigned", "void",   "WriteLine",
                       next_param_type="string"),
        ]
        errors = self.planner.validate_plan(plan)
        self.assertEqual(errors, [])

    def test_void_output_skips_type_check(self):
        """
        void を返すステップは次ステップへの型接続が存在しないため、
        後続ステップの引数型がなんであってもエラーにならない。
        """
        plan = [
            _make_step("PERSIST", "assigned", "void", "WriteAllText"),
            _make_step("DISPLAY", "assigned", "void", "WriteLine",
                       next_param_type="IEnumerable<Order>"),
        ]
        errors = self.planner.validate_plan(plan)
        self.assertEqual(errors, [])

    def test_no_param_next_step_skips_type_check(self):
        """
        次ステップのメソッドが引数を持たない場合は型接続チェック対象外。
        エラーなし。
        """
        plan = [
            _make_step("FETCH",     "assigned", "IEnumerable<Product>", "GetProducts"),
            # next_param_type=None → params=[]
            _make_step("PERSIST",   "assigned", "void", "SaveNoArgs"),
        ]
        errors = self.planner.validate_plan(plan)
        self.assertEqual(errors, [])

    # ------------------------------------------------------------------
    # Bridge Case（アダプタ変換が必要なケース）
    # ------------------------------------------------------------------

    def test_bridge_conversion_attaches_adapter(self):
        """
        TypeSystem の bridges に定義された変換（decimal → string）が必要な場合、
        次ステップに adapter キーが付加される。エラーにはならない。
        """
        plan = [
            _make_step("CALC",    "assigned", "decimal", "CalculateDiscount"),
            _make_step("DISPLAY", "assigned", "void",    "WriteLine",
                       next_param_type="string"),
        ]
        errors = self.planner.validate_plan(plan)
        # bridges に decimal→string があるので互換。ただしアダプタが必要。
        self.assertEqual(errors, [])
        adapter = plan[1].get("adapter")
        self.assertIsNotNone(adapter, "adapter should be attached for bridge conversion")
        self.assertIn("expression", adapter)
        self.assertIn("{var}", adapter["expression"],
                      "adapter expression should use {var} placeholder")
        self.assertEqual(adapter["source_type"], "decimal")
        self.assertEqual(adapter["target_type"], "string")

    def test_object_wildcard_is_compatible_without_adapter(self):
        """
        object を受け取るメソッドはどんな型も受け付ける（スコアは低いが互換）。
        エラーなし、アダプタなし。
        """
        plan = [
            _make_step("FETCH",   "assigned", "IEnumerable<User>", "GetUsers"),
            _make_step("DISPLAY", "assigned", "void",              "WriteLine",
                       next_param_type="object"),
        ]
        errors = self.planner.validate_plan(plan)
        self.assertEqual(errors, [])

    # ------------------------------------------------------------------
    # Mismatch Case（型不一致エラーのケース）
    # ------------------------------------------------------------------

    def test_incompatible_types_returns_error(self):
        """
        IEnumerable<User> を bool 引数へ渡そうとした場合は型不一致エラー。
        TypeSystem の hierarchy にも bridges にも対応する変換がない。

        Note: IEnumerable<User> → string は TypeSystem.bridges に
        JsonSerializer.Serialize({var}) が定義されているため互換（アダプタ付き）となる。
        ここでは bridges に存在しない bool を対象とする。
        """
        plan = [
            _make_step("FETCH",    "assigned", "IEnumerable<User>", "GetUsers"),
            _make_step("EXISTS",   "assigned", "void",              "FileExists",
                       next_param_type="bool"),
        ]
        errors = self.planner.validate_plan(plan)
        self.assertGreater(len(errors), 0, "Should detect type mismatch")
        self.assertIn("type_error", plan[1])
        type_err = plan[1]["type_error"]
        self.assertEqual(type_err["source_type"], "IEnumerable<User>")
        self.assertEqual(type_err["expected_type"], "bool")


    def test_bool_to_collection_is_incompatible(self):
        """bool → IEnumerable<T> は互換性なし。エラーが検出される。"""
        plan = [
            _make_step("EXISTS",  "assigned", "bool",                "Exists"),
            _make_step("DISPLAY", "assigned", "void",                "Render",
                       next_param_type="IEnumerable<T>"),
        ]
        errors = self.planner.validate_plan(plan)
        self.assertGreater(len(errors), 0)
        self.assertIn("type_error", plan[1])

    # ------------------------------------------------------------------
    # Missing Method Case（メソッド未割り当てのケース）
    # ------------------------------------------------------------------

    def test_missing_step_reports_error(self):
        """status='missing' のステップはエラーメッセージに含まれる。"""
        plan = [
            {
                "task": "FETCH",
                "entity": "Order",
                "status": "missing",
                "error": "No suitable method found",
            }
        ]
        errors = self.planner.validate_plan(plan)
        self.assertGreater(len(errors), 0)
        self.assertIn("missing", errors[0].lower())
        self.assertIn("FETCH", errors[0])

    def test_mixed_assigned_and_missing(self):
        """
        最初のステップが assigned でも、次が missing なら
        型チェックをスキップし missing エラーのみ報告する。
        """
        plan = [
            _make_step("FETCH",   "assigned", "IEnumerable<User>", "GetUsers"),
            {
                "task": "TRANSFORM",
                "entity": "User",
                "status": "missing",
                "error": "No method for TRANSFORM",
            },
        ]
        errors = self.planner.validate_plan(plan)
        # missing エラー1件のみ（型不一致エラーは出ない）
        self.assertEqual(len(errors), 1)
        self.assertIn("missing", errors[0].lower())

    # ------------------------------------------------------------------
    # Multi-step Chain（複数ステップの連鎖チェック）
    # ------------------------------------------------------------------

    def test_three_step_chain_all_compatible(self):
        """
        3ステップチェーン: FETCH → TRANSFORM → PERSIST が全て互換なら
        エラーなし。
        """
        plan = [
            _make_step("FETCH",     "assigned", "IEnumerable<User>", "GetUsers"),
            _make_step("TRANSFORM", "assigned", "IEnumerable<User>", "Where",
                       next_param_type="IEnumerable<T>"),
            # PERSIST の引数は 3ステップ目が持つ param
            _make_step("PERSIST",   "assigned", "void",              "WriteAllText",
                       next_param_type="IEnumerable<T>"),
        ]
        errors = self.planner.validate_plan(plan)
        self.assertEqual(errors, [])

    def test_three_step_chain_middle_mismatch_detected(self):
        """
        3ステップチェーンで中間の型が不一致の場合、その箇所のみエラー。
        """
        plan = [
            _make_step("FETCH",     "assigned", "IEnumerable<User>", "GetUsers"),
            # bool を返すメソッドの後に IEnumerable<T> を要求 → 不一致
            _make_step("EXISTS",    "assigned", "bool",              "FileExists",
                       next_param_type="IEnumerable<T>"),
            _make_step("DISPLAY",   "assigned", "void",              "Render",
                       next_param_type="IEnumerable<T>"),
        ]
        errors = self.planner.validate_plan(plan)
        # step2→step3 の型不一致を検出
        self.assertGreater(len(errors), 0)
        self.assertIn("type_error", plan[2])


if __name__ == "__main__":
    unittest.main()
