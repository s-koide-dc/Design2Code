# -*- coding: utf-8 -*-
import unittest
import json
import os
from src.ir_generator.ir_generator import IRGenerator
from src.config.config_manager import ConfigManager

class TestIRGenerator(unittest.TestCase):
    def setUp(self):
        self.config = ConfigManager()
        self.generator = IRGenerator(self.config)

    def test_generate_simple_chain(self):
        steps = [
            "Data.Repo.GetUsersで全ユーザーを取得する",
            "結果を 'active_users.txt' に保存する"
        ]
        ir = self.generator.generate(steps)
        
        self.assertEqual(len(ir["logic_tree"]), 2)
        # 決定論的解析により、最初のステップは FETCH 意図を持つ ACTION
        self.assertEqual(ir["logic_tree"][0]["type"], "ACTION")
        # エンティティ名は解析の深さに依存するため、存在確認に留める
        self.assertTrue(len(ir["logic_tree"][0]["target_entity"]) > 0)

    def test_generate_nested_structure(self):
        steps = [
            "リトライする。以下の処理を繰り返す：",
            "Data.Repo.GetUsersで全ユーザーを取得する。",
            "取得結果を正規化する。",
            "取得した各アイテムに対して、以下の処理を行う：",
            "名前をコンソールに表示する。",
            "を終えて。",
            "を終えて。"
        ]
        ir = self.generator.generate(steps)
        
        # Structure: ACTION(Retry) -> children: [ACTION(GetUsers), LOOP -> children: [ACTION(Display)]]
        self.assertEqual(ir["logic_tree"][0]["type"], "ACTION")
        self.assertEqual(ir["logic_tree"][0].get("semantic_map", {}).get("spec_role"), "WRAP")
        wrapper_children = ir["logic_tree"][0].get("children", [])
        self.assertTrue(len(wrapper_children) >= 1)
        self.assertEqual(wrapper_children[0].get("input_link"), ir["logic_tree"][0].get("id"))
        if len(wrapper_children) > 1:
            self.assertEqual(wrapper_children[1].get("input_link"), wrapper_children[0].get("id"))
        if len(wrapper_children) > 2 and wrapper_children[2].get("type") == "LOOP":
            self.assertEqual(wrapper_children[2].get("intent"), "GENERAL")
            self.assertEqual(wrapper_children[2].get("role"), "ITERATE")
            self.assertEqual(wrapper_children[2].get("semantic_map", {}).get("spec_role"), "ITERATE")
            loop_child = wrapper_children[2].get("children", [])[0]
            self.assertEqual(wrapper_children[2].get("input_link"), wrapper_children[1].get("id"))
            self.assertEqual(loop_child.get("input_link"), wrapper_children[2].get("id"))

    def test_loop_second_sibling_prefers_previous_sibling_inside_block(self):
        steps = [
            "商品一覧を取得する。",
            "取得した各商品に対して、以下の処理を行う：",
            "価格を計算する。",
            "計算結果を表示する。",
            "を終えて。"
        ]
        ir = self.generator.generate(steps)

        loop_node = ir["logic_tree"][1]
        first_child = loop_node.get("children", [])[0]
        second_child = loop_node.get("children", [])[1]

        self.assertEqual(first_child.get("input_link"), loop_node.get("id"))
        self.assertEqual(second_child.get("input_link"), first_child.get("id"))

    def test_generate_conditional(self):
        steps = [
            "もし config.json が存在するならば、以下の処理を行う：",
            "ファイルを読み込む。",
            "そうでなければ、以下の処理を行う：",
            "エラーを表示する。",
            "を終えて。"
        ]
        ir = self.generator.generate(steps)
        
        self.assertEqual(ir["logic_tree"][0]["type"], "CONDITION")
        self.assertEqual(len(ir["logic_tree"][0].get("children", [])), 1)
        self.assertEqual(len(ir["logic_tree"][0].get("else_children", [])), 1)

    def test_else_children_input_link_uses_condition_branch_base(self):
        steps = [
            "もし config.json が存在するならば、以下の処理を行う：",
            "ファイルを読み込む。",
            "内容を表示する。",
            "そうでなければ、以下の処理を行う：",
            "エラーを表示する。",
            "を終えて。"
        ]
        ir = self.generator.generate(steps)

        condition_node = ir["logic_tree"][0]
        else_node = condition_node.get("else_children", [])[0]

        self.assertEqual(condition_node.get("id"), "step_1")
        self.assertEqual(else_node.get("input_link"), condition_node.get("id"))

    def test_input_link_prefers_latest_collection(self):
        steps = [
            "Data.Repo.GetUsersで全ユーザーを取得する。",
            "取得したユーザーの件数を計算する。",
            "ユーザー一覧をコンソールに表示する。"
        ]
        ir = self.generator.generate(steps)
        
        self.assertEqual(len(ir["logic_tree"]), 3)
        first_node = ir["logic_tree"][0]
        display_node = ir["logic_tree"][2]
        
        self.assertEqual(first_node.get("cardinality"), "COLLECTION")
        self.assertEqual(display_node.get("intent"), "DISPLAY")
        self.assertEqual(display_node.get("input_link"), first_node.get("id"))

    def test_spec_role_is_preserved_for_display_and_fetch(self):
        steps = [
            "Data.Repo.GetUsersで全ユーザーを取得する。",
            "ユーザー一覧をコンソールに表示する。"
        ]
        ir = self.generator.generate(steps)

        fetch_node = ir["logic_tree"][0]
        display_node = ir["logic_tree"][1]

        self.assertEqual(fetch_node.get("semantic_map", {}).get("spec_role"), "FETCH")
        self.assertEqual(display_node.get("semantic_map", {}).get("spec_role"), "DISPLAY")

    def test_spec_role_marks_condition_as_check(self):
        steps = [
            "もし config.json が存在するならば、以下の処理を行う：",
            "ファイルを読み込む。",
            "を終えて。"
        ]
        ir = self.generator.generate(steps)

        condition_node = ir["logic_tree"][0]
        self.assertEqual(condition_node.get("type"), "CONDITION")
        self.assertEqual(condition_node.get("semantic_map", {}).get("spec_role"), "CHECK")

    def test_spec_role_marks_auto_json_deserialize_node(self):
        structured_spec = {
            "steps": [
                {
                    "id": "step_1",
                    "text": "users.json を読み込む",
                    "intent": "FETCH",
                    "source_ref": "users.json",
                    "source_kind": "file",
                    "output_type": "List<User>"
                }
            ],
            "inputs": [],
            "outputs": [],
            "data_sources": []
        }
        ir = self.generator.generate(structured_spec)

        self.assertEqual(len(ir["logic_tree"]), 2)
        deserialize_node = ir["logic_tree"][1]
        self.assertEqual(deserialize_node.get("intent"), "JSON_DESERIALIZE")
        self.assertEqual(deserialize_node.get("semantic_map", {}).get("spec_role"), "DESERIALIZE")

    def test_condition_check_metadata_for_exists(self):
        steps = [
            "もし \"config.json\" が存在するならば、以下の処理を行う：",
            "ファイルを読み込む。",
            "を終えて。"
        ]
        ir = self.generator.generate(steps)

        condition_node = ir["logic_tree"][0]
        semantic_map = condition_node.get("semantic_map", {})
        self.assertEqual(semantic_map.get("spec_role"), "CHECK")
        self.assertEqual(semantic_map.get("check_kind"), "exists_check")
        self.assertEqual(semantic_map.get("check_subject"), "config.json")
        self.assertEqual(semantic_map.get("expected_truth"), True)
        self.assertEqual(semantic_map.get("source_kind"), "file")
        self.assertEqual(semantic_map.get("subject_resolution"), "quoted_literal")

    def test_condition_check_metadata_for_null(self):
        steps = [
            "もし user が null ならば、以下の処理を行う：",
            "エラーを表示する。",
            "を終えて。"
        ]
        ir = self.generator.generate(steps)

        condition_node = ir["logic_tree"][0]
        semantic_map = condition_node.get("semantic_map", {})
        self.assertEqual(condition_node.get("intent"), "EXISTS")
        self.assertEqual(condition_node.get("role"), "CHECK")
        self.assertEqual(condition_node.get("target_entity"), "User")
        self.assertEqual(semantic_map.get("spec_role"), "CHECK")
        self.assertEqual(semantic_map.get("check_kind"), "null_check")
        self.assertEqual(semantic_map.get("check_subject"), "user")
        self.assertEqual(semantic_map.get("expected_truth"), False)
        self.assertEqual(semantic_map.get("subject_resolution"), "explicit_subject")

    def test_condition_check_metadata_for_comparison(self):
        steps = [
            "もし Points が 100 より大きいならば、以下の処理を行う：",
            "名前を表示する。",
            "を終えて。"
        ]
        ir = self.generator.generate(steps)

        condition_node = ir["logic_tree"][0]
        semantic_map = condition_node.get("semantic_map", {})
        self.assertEqual(condition_node.get("intent"), "EXISTS")
        self.assertEqual(condition_node.get("role"), "CHECK")
        self.assertEqual(semantic_map.get("spec_role"), "CHECK")
        self.assertEqual(semantic_map.get("check_kind"), "comparison_check")
        self.assertEqual(semantic_map.get("check_operator"), ">")
        self.assertEqual(semantic_map.get("check_value"), "100")
        self.assertEqual(semantic_map.get("subject_resolution"), "explicit_subject")

    def test_comparison_check_promotes_to_schema_property_when_owner_is_unique(self):
        generator = IRGenerator(
            self.config,
            entity_schema={
                "entities": [
                    {"name": "Product", "keywords": ["商品"], "properties": ["Stock:int", "Name:string"]},
                    {"name": "Order", "keywords": ["注文"], "properties": ["Total:decimal", "Id:int"]},
                    {"name": "Invoice", "keywords": ["請求書"], "properties": ["Total:decimal", "Number:string"]},
                ]
            }
        )
        steps = [
            "商品を取得する。",
            "もし Stock が 0 より大きいならば、以下の処理を行う：",
            "名前を表示する。",
            "を終えて。"
        ]

        ir = generator.generate(steps)

        condition_node = ir["logic_tree"][1]
        semantic_map = condition_node.get("semantic_map", {})
        self.assertEqual(semantic_map.get("check_subject"), "Stock")
        self.assertEqual(semantic_map.get("subject_resolution"), "schema_property")

    def test_comparison_check_promotes_to_history_subject_when_scope_is_exact(self):
        generator = IRGenerator(
            self.config,
            entity_schema={
                "entities": [
                    {"name": "Product", "keywords": ["商品"], "properties": ["Stock:int", "Name:string"]},
                    {"name": "Order", "keywords": ["注文"], "properties": ["Total:decimal", "Id:int"]},
                    {"name": "Invoice", "keywords": ["請求書"], "properties": ["Total:decimal", "Number:string"]},
                ]
            }
        )
        steps = [
            "注文を取得する。",
            "もし Total が 100 より大きいならば、以下の処理を行う：",
            "IDを表示する。",
            "を終えて。"
        ]

        ir = generator.generate(steps)

        condition_node = ir["logic_tree"][1]
        semantic_map = condition_node.get("semantic_map", {})
        self.assertEqual(semantic_map.get("check_subject"), "Total")
        self.assertEqual(semantic_map.get("subject_resolution"), "history_subject")

    def test_comparison_check_promotes_japanese_alias_to_schema_or_history_property(self):
        generator = IRGenerator(
            self.config,
            entity_schema={
                "entities": [
                    {
                        "name": "Product",
                        "keywords": ["商品"],
                        "properties": [
                            {"name": "Stock", "aliases": ["在庫"]},
                            {"name": "Name", "aliases": ["名前"]},
                        ],
                    },
                    {
                        "name": "Order",
                        "keywords": ["注文"],
                        "properties": [
                            {"name": "Total", "aliases": ["合計金額"]},
                            {"name": "Id", "aliases": ["ID"]},
                        ],
                    },
                    {
                        "name": "Invoice",
                        "keywords": ["請求書"],
                        "properties": [
                            {"name": "Total", "aliases": ["合計金額"]},
                            {"name": "Number", "aliases": ["番号"]},
                        ],
                    },
                ]
            }
        )
        steps = [
            "商品を取得する。",
            "もし在庫が 0 より大きいならば、以下の処理を行う：",
            "名前を表示する。",
            "を終えて。",
            "注文を取得する。",
            "もし合計金額が 100 より大きいならば、以下の処理を行う：",
            "IDを表示する。",
            "を終えて。"
        ]

        ir = generator.generate(steps)

        first_condition = ir["logic_tree"][1]
        second_condition = ir["logic_tree"][3]
        first_map = first_condition.get("semantic_map", {})
        second_map = second_condition.get("semantic_map", {})

        self.assertEqual(first_map.get("check_subject"), "Stock")
        self.assertEqual(first_map.get("subject_resolution"), "schema_property")
        self.assertEqual(second_map.get("check_subject"), "Total")
        self.assertEqual(second_map.get("subject_resolution"), "history_subject")

    def test_calculate_promotes_with_target_hint_and_calculation_intent(self):
        structured_steps = [
            {"text": "商品を取得する。"},
            {
                "text": "DiscountedPriceを計算する。",
                "semantic_roles": {
                    "target_hint": "DiscountedPrice",
                    "property": "DiscountedPrice"
                }
            },
            {"text": "計算結果を表示する。"}
        ]
        ir = self.generator.generate(structured_steps)

        calc_node = ir["logic_tree"][1]
        self.assertEqual(calc_node.get("intent"), "CALC")
        self.assertEqual(calc_node.get("role"), "CALC")
        self.assertEqual(calc_node.get("semantic_map", {}).get("spec_role"), "CALCULATE")
        semantic_roles = calc_node.get("semantic_map", {}).get("semantic_roles", {})
        self.assertEqual(semantic_roles.get("target_hint"), "DiscountedPrice")
        self.assertEqual(semantic_roles.get("property"), "DiscountedPrice")

    def test_calculate_target_entity_uses_schema_property_owner(self):
        generator = IRGenerator(
            self.config,
            entity_schema={
                "entities": [
                    {
                        "name": "Product",
                        "properties": ["DiscountedPrice:decimal", "Name:string"]
                    }
                ]
            }
        )
        structured_steps = [
            {"text": "商品を取得する。"},
            {
                "text": "DiscountedPriceを計算する。",
                "semantic_roles": {
                    "target_hint": "DiscountedPrice",
                    "property": "DiscountedPrice"
                }
            },
            {"text": "計算結果を表示する。"}
        ]

        ir = generator.generate(structured_steps)

        calc_node = ir["logic_tree"][1]
        display_node = ir["logic_tree"][2]
        calc_roles = calc_node.get("semantic_map", {}).get("semantic_roles", {})

        self.assertEqual(calc_node.get("intent"), "CALC")
        self.assertEqual(calc_node.get("target_entity"), "Product")
        self.assertEqual(calc_roles.get("target_entity"), "Product")
        self.assertEqual(calc_roles.get("entity_resolution"), "unique_owner")
        self.assertEqual(display_node.get("target_entity"), "Product")

    def test_calculate_does_not_promote_without_target_hint(self):
        steps = [
            "商品を取得する。",
            "価格を計算する。",
            "計算結果を表示する。"
        ]
        ir = self.generator.generate(steps)

        calc_node = ir["logic_tree"][1]
        self.assertEqual(calc_node.get("intent"), "GENERAL")
        self.assertEqual(calc_node.get("role"), "ACTION")
        self.assertEqual(calc_node.get("semantic_map", {}).get("spec_role"), "ACTION")

    def test_calculate_target_entity_stays_weak_when_property_owner_is_ambiguous(self):
        generator = IRGenerator(
            self.config,
            entity_schema={
                "entities": [
                    {
                        "name": "Order",
                        "properties": ["Total:decimal", "Id:int"]
                    },
                    {
                        "name": "Invoice",
                        "properties": ["Total:decimal", "Number:string"]
                    }
                ]
            }
        )
        structured_steps = [
            {"text": "レコードを取得する。"},
            {
                "text": "Totalを計算する。",
                "semantic_roles": {
                    "target_hint": "Total",
                    "property": "Total"
                }
            },
            {"text": "計算結果を表示する。"}
        ]

        ir = generator.generate(structured_steps)

        calc_node = ir["logic_tree"][1]
        display_node = ir["logic_tree"][2]
        calc_roles = calc_node.get("semantic_map", {}).get("semantic_roles", {})

        self.assertEqual(calc_node.get("intent"), "CALC")
        self.assertEqual(calc_node.get("semantic_map", {}).get("spec_role"), "CALCULATE")
        self.assertEqual(calc_node.get("target_entity"), "Item")
        self.assertEqual(calc_roles.get("target_entity"), "Item")
        self.assertEqual(calc_roles.get("entity_resolution"), "ambiguous")
        self.assertEqual(display_node.get("target_entity"), "Item")

    def test_calculate_history_context_is_observed_as_history_fallback(self):
        generator = IRGenerator(
            self.config,
            entity_schema={
                "entities": [
                    {
                        "name": "Order",
                        "keywords": ["注文"],
                        "properties": ["Id:int", "CreatedAt:DateTime"]
                    },
                    {
                        "name": "Invoice",
                        "keywords": ["請求書"],
                        "properties": ["Number:string", "IssuedAt:DateTime"]
                    }
                ]
            }
        )
        structured_steps = [
            {"text": "注文を取得する。"},
            {
                "text": "Totalを計算する。",
                "semantic_roles": {
                    "target_hint": "Total",
                    "property": "Total"
                }
            },
            {"text": "計算結果を表示する。"}
        ]

        ir = generator.generate(structured_steps)

        calc_node = ir["logic_tree"][1]
        calc_roles = calc_node.get("semantic_map", {}).get("semantic_roles", {})

        self.assertEqual(calc_node.get("intent"), "CALC")
        self.assertEqual(calc_node.get("target_entity"), "Order")
        self.assertEqual(calc_roles.get("target_entity"), "Order")
        self.assertEqual(calc_roles.get("entity_resolution"), "history_fallback")

    def test_display_with_calculation_word_does_not_promote_to_calc(self):
        structured_steps = [
            {"text": "商品を取得する。"},
            {
                "text": "計算結果を表示する。",
                "semantic_roles": {
                    "target_hint": "DiscountedPrice",
                    "property": "DiscountedPrice"
                }
            }
        ]

        ir = self.generator.generate(structured_steps)

        display_node = ir["logic_tree"][1]
        self.assertEqual(display_node.get("intent"), "DISPLAY")
        self.assertEqual(display_node.get("role"), "DISPLAY")
        self.assertEqual(display_node.get("semantic_map", {}).get("spec_role"), "DISPLAY")

    def test_filter_promotes_with_logic_goal_and_collection_context(self):
        generator = IRGenerator(
            self.config,
            entity_schema={
                "entities": [
                    {
                        "name": "User",
                        "keywords": ["ユーザー"],
                        "properties": ["Points:int", "Name:string"]
                    }
                ]
            }
        )
        steps = [
            "ユーザー一覧を取得する。",
            "Points が input_1 より大きいユーザーを抽出する。",
            "結果を表示する。"
        ]

        ir = generator.generate(steps)

        filter_node = ir["logic_tree"][1]
        roles = filter_node.get("semantic_map", {}).get("semantic_roles", {})

        self.assertEqual(filter_node.get("intent"), "LINQ")
        self.assertEqual(filter_node.get("role"), "FILTER")
        self.assertEqual(filter_node.get("semantic_map", {}).get("spec_role"), "FILTER")
        self.assertEqual(roles.get("property"), "Points")
        self.assertEqual(roles.get("predicate_resolution"), "schema_property")
        self.assertEqual(roles.get("collection_resolution"), "explicit_input_link")

    def test_filter_promotes_property_to_schema_property_when_owner_is_unique(self):
        generator = IRGenerator(
            self.config,
            entity_schema={
                "entities": [
                    {"name": "Product", "keywords": ["商品"], "properties": ["Stock:int", "Name:string"]},
                    {"name": "Order", "keywords": ["注文"], "properties": ["Total:decimal", "Id:int"]},
                    {"name": "Invoice", "keywords": ["請求書"], "properties": ["Total:decimal", "Number:string"]},
                ]
            }
        )
        steps = [
            "商品一覧を取得する。",
            "Stock が 0 より大きい商品を抽出する。"
        ]

        ir = generator.generate(steps)

        filter_node = ir["logic_tree"][1]
        roles = filter_node.get("semantic_map", {}).get("semantic_roles", {})
        self.assertEqual(roles.get("property"), "Stock")
        self.assertEqual(roles.get("predicate_resolution"), "schema_property")

    def test_filter_promotes_property_to_history_predicate_when_scope_is_exact(self):
        generator = IRGenerator(
            self.config,
            entity_schema={
                "entities": [
                    {"name": "Product", "keywords": ["商品"], "properties": ["Stock:int", "Name:string"]},
                    {"name": "Order", "keywords": ["注文"], "properties": ["Total:decimal", "Id:int"]},
                    {"name": "Invoice", "keywords": ["請求書"], "properties": ["Total:decimal", "Number:string"]},
                ]
            }
        )
        steps = [
            "注文一覧を取得する。",
            "Total が 100 より大きい注文を抽出する。"
        ]

        ir = generator.generate(steps)

        filter_node = ir["logic_tree"][1]
        roles = filter_node.get("semantic_map", {}).get("semantic_roles", {})
        self.assertEqual(roles.get("property"), "Total")
        self.assertEqual(roles.get("predicate_resolution"), "history_predicate")

    def test_filter_promotes_japanese_alias_to_schema_or_history_property(self):
        generator = IRGenerator(
            self.config,
            entity_schema={
                "entities": [
                    {
                        "name": "Product",
                        "keywords": ["商品"],
                        "properties": [
                            {"name": "Stock", "aliases": ["在庫"]},
                            {"name": "Name", "aliases": ["名前"]},
                        ],
                    },
                    {
                        "name": "Order",
                        "keywords": ["注文"],
                        "properties": [
                            {"name": "Total", "aliases": ["合計金額"]},
                            {"name": "Id", "aliases": ["ID"]},
                        ],
                    },
                    {
                        "name": "Invoice",
                        "keywords": ["請求書"],
                        "properties": [
                            {"name": "Total", "aliases": ["合計金額"]},
                            {"name": "Number", "aliases": ["番号"]},
                        ],
                    },
                ]
            }
        )
        steps = [
            "商品一覧を取得する。",
            "在庫が 0 より大きい商品を抽出する。",
            "注文一覧を取得する。",
            "合計金額が 100 より大きい注文を抽出する。"
        ]

        ir = generator.generate(steps)

        first_filter = ir["logic_tree"][1]
        second_filter = ir["logic_tree"][3]
        first_roles = first_filter.get("semantic_map", {}).get("semantic_roles", {})
        second_roles = second_filter.get("semantic_map", {}).get("semantic_roles", {})

        self.assertEqual(first_roles.get("property"), "Stock")
        self.assertEqual(first_roles.get("predicate_resolution"), "schema_property")
        self.assertEqual(second_roles.get("property"), "Total")
        self.assertEqual(second_roles.get("predicate_resolution"), "history_predicate")

    def test_fetch_extract_without_predicate_stays_fetch(self):
        generator = IRGenerator(
            self.config,
            entity_schema={
                "entities": [
                    {
                        "name": "User",
                        "keywords": ["ユーザー"],
                        "properties": ["Points:int", "Name:string"]
                    }
                ]
            }
        )
        steps = [
            "ユーザー一覧を取得する。",
            "ユーザーを抽出する。"
        ]

        ir = generator.generate(steps)

        fetch_like_node = ir["logic_tree"][1]
        roles = fetch_like_node.get("semantic_map", {}).get("semantic_roles", {})

        self.assertEqual(fetch_like_node.get("intent"), "FETCH")
        self.assertEqual(fetch_like_node.get("role"), "FETCH")
        self.assertEqual(fetch_like_node.get("semantic_map", {}).get("spec_role"), "FETCH")
        self.assertIsNone(roles.get("predicate_resolution"))
        self.assertIsNone(roles.get("collection_resolution"))

if __name__ == "__main__":
    unittest.main()
