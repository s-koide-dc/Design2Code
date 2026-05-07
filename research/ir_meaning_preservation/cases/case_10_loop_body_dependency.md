# Case 10: Loop Body Dependency

## Source Scenario

- Scenario: `BatchProcessProducts.design.md` を拡張した loop body 依存観察ケース
- Benchmark role: `LOOP` 配下の `first-child` / `second sibling` / `nested child`

## Target Meaning Elements

- loop body first-child の loop 親依存
- loop body second sibling の逐次 sibling 依存
- nested condition 配下 first-child の nested 構造親依存

## Expected Structure Summary

- 商品集合を反復する
- loop 内最初のノードで価格を計算する
- 次のノードで計算結果を表示する
- その後 nested condition で在庫を確認し、true 側で補足表示を行う

## Expected IR

```json
{
  "case_id": "case_10_loop_body_dependency",
  "status": "draft",
  "module_name": "LoopBodyDependency",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "Product",
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<Product>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "FETCH"
        }
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_2",
      "type": "LOOP",
      "intent": "GENERAL",
      "role": "ITERATE",
      "target_entity": "Product",
      "cardinality": "COLLECTION",
      "output_type": "void",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "ITERATE"
        }
      },
      "children": [
        {
          "id": "step_3",
          "type": "ACTION",
          "intent": "CALC",
          "role": "CALC",
          "target_entity": "Product",
          "cardinality": "SINGLE",
          "output_type": "decimal",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": "step_2",
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "spec_role": "CALCULATE",
              "property": "DiscountedPrice"
            }
          },
          "children": [],
          "else_children": []
        },
        {
          "id": "step_4",
          "type": "ACTION",
          "intent": "DISPLAY",
          "role": "DISPLAY",
          "target_entity": "Product",
          "cardinality": "SINGLE",
          "output_type": "string",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": "step_3",
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "spec_role": "DISPLAY",
              "property": "DiscountedPrice"
            }
          },
          "children": [],
          "else_children": []
        },
        {
          "id": "step_5",
          "type": "CONDITION",
          "intent": "EXISTS",
          "role": "CHECK",
          "target_entity": "Product",
          "cardinality": "SINGLE",
          "output_type": "bool",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": "step_4",
          "condition_expression": "product.Stock > 0",
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "spec_role": "CHECK",
              "property": "Stock"
            },
            "check_kind": "comparison_check",
            "check_subject": "Stock",
            "check_operator": ">",
            "check_value": "0",
            "expected_truth": true
          },
          "children": [
            {
              "id": "step_6",
              "type": "ACTION",
              "intent": "DISPLAY",
              "role": "DISPLAY",
              "target_entity": "Product",
              "cardinality": "SINGLE",
              "output_type": "string",
              "source_kind": "memory",
              "source_ref": null,
              "input_link": "step_5",
              "semantic_map": {
                "logic": [],
                "semantic_roles": {
                  "spec_role": "DISPLAY",
                  "message": "in stock"
                }
              },
              "children": [],
              "else_children": []
            }
          ],
          "else_children": []
        }
      ],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- loop body first-child は `input_link = loop`
- loop body second sibling は `input_link = first_child`
- nested condition 自体は loop body sibling として接続される
- nested condition の子 first-child は `input_link = nested_condition`

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_10_loop_body_dependency.observed.json`
```

## Diff Notes

- loop body first-child は期待どおり `input_link = step_2`
- loop body second sibling も `input_link = step_3` に改善し、逐次 sibling 依存が成立した
- nested condition child first-child も期待どおり `input_link = step_5`
- `CALC` が `GENERAL/ACTION` に弱化し、loop ノードも `FETCH/FETCH` に寄っている
- 依存規則は改善したが、構造 role と計算 role の保持はまだ弱い

## Failure Mapping

- Primary: `Intent Drift`
- Secondary: `Under-Spec Capture`
