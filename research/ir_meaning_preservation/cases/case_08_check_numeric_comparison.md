# Case 08: Check Numeric Comparison

## Source Scenario

- Scenario: `scenarios/ProcessActiveUsers.design.md` と `scenarios/CalculateOrderDiscount.design.md` の比較条件パターンを抽象化
- Benchmark role: `comparison_check` の最小ケース

## Target Meaning Elements

- 数値比較条件の保持
- `CHECK` と `FILTER` の境界
- 比較演算子と比較対象値の保持

## Expected Structure Summary

- ユーザー一覧を取得する
- 各ユーザーの `Points` が `input_1` より大きいかを確認する
- true の場合のみ名前を表示する

## Expected IR

```json
{
  "case_id": "case_08_check_numeric_comparison",
  "status": "draft",
  "module_name": "CheckNumericComparison",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "User",
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<User>",
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
      "target_entity": "User",
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
          "id": "step_2_1",
          "type": "CONDITION",
          "intent": "EXISTS",
          "role": "CHECK",
          "target_entity": "User",
          "cardinality": "SINGLE",
          "output_type": "bool",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": "step_1",
          "condition_expression": "item.Points > input_1",
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "spec_role": "CHECK",
              "property": "Points"
            },
            "check_kind": "comparison_check",
            "check_subject": "Points",
            "check_operator": ">",
            "check_value": "input_1",
            "expected_truth": true
          },
          "children": [
            {
              "id": "step_2_2",
              "type": "ACTION",
              "intent": "DISPLAY",
              "role": "DISPLAY",
              "target_entity": "User",
              "cardinality": "SINGLE",
              "output_type": "string",
              "source_kind": "memory",
              "source_ref": null,
              "input_link": "step_2_1",
              "semantic_map": {
                "logic": [],
                "semantic_roles": {
                  "spec_role": "DISPLAY",
                  "property": "Name"
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

- このケースは `FILTER` ではなく `CHECK` の観察用に、明示的な loop 内 condition として置く
- `check_operator` と `check_value` が downstream 条件式生成の鍵になる
- `Points > input_1` の比較情報を role 弱化で失わないことが重要

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_08_check_numeric_comparison.observed.json`
```

## Diff Notes

- `check_kind=comparison_check`, `check_operator=>`, `check_value=100` は期待どおり保持された
- 比較条件ノードは `CONDITION` として loop 内に保持された
- 条件ノードの `intent/role` は `EXISTS/CHECK` まで改善した
- `target_entity` は `User` ではなく `Item`
- 生成条件式は `x.Points > 100` となり、比較意味と loop 文脈の両方が反映された
- 親 loop ノードは依然として `intent=FETCH`, `role=FETCH` で、`ITERATE` 意味の runtime 側整合は未解決

## Failure Mapping

- Primary: `Under-Spec Capture`
- Secondary: `None`
