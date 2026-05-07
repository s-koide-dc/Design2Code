# Case 15: Calculate History Fallback Gap

## Source Scenario

- Scenario: 直前文脈の entity を使って `CALCULATE` したいが、property owner schema は与えないケース
- Benchmark role: upstream で `history_fallback` が純粋に観測できるかの確認

## Target Meaning Elements

- `history_fallback` と `explicit_entity` の境界
- `_identify_target_entity` の文脈継承と `entity_resolution` の責務分離
- upstream と downstream の resolution model の一致性

## Expected Structure Summary

- 注文を取得する
- `Total` を計算する
- 計算結果を表示する

## Expected IR

```json
{
  "case_id": "case_15_calculate_history_fallback_gap",
  "status": "draft",
  "module_name": "CalculateHistoryFallbackGap",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "Order",
      "cardinality": "SINGLE",
      "output_type": null,
      "source_kind": "memory",
      "source_ref": null,
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "Order"
        },
        "spec_role": "FETCH"
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_2",
      "type": "ACTION",
      "intent": "CALC",
      "role": "CALC",
      "target_entity": "Order",
      "cardinality": "SINGLE",
      "output_type": null,
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "Order",
          "target_hint": "Total",
          "property": "Total",
          "entity_resolution": "history_fallback"
        },
        "spec_role": "CALCULATE"
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_3",
      "type": "ACTION",
      "intent": "DISPLAY",
      "role": "DISPLAY",
      "target_entity": "Order",
      "cardinality": "SINGLE",
      "output_type": "string",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_2",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "Order"
        },
        "spec_role": "DISPLAY"
      },
      "children": [],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- property owner schema がないため `unique_owner` にはならない
- それでも直前の `Order` 文脈を継承して `CALCULATE` を扱いたいので、理想的には `entity_resolution=history_fallback`
- これは `explicit_entity` とは区別して観測したい

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_15_calculate_history_fallback_gap.observed.json`
```

## Diff Notes

- 観測上は `target_entity=Order` が保持された
- `entity_resolution` も期待どおり `history_fallback` になった
- これは、一般の `target_entity` 推定と `CALCULATE` 用 `entity_resolution` 判定で history fallback の責務を分離したためである
- 具体的には、`semantic_roles.target_entity` には no-history の base inference を保持し、その後段でのみ history 由来の補正を適用している
- そのため後続 `DISPLAY` では、ノード全体の `target_entity` は `Order` に寄る一方、`semantic_roles.target_entity` は base 値の `Item` に留まる

## Failure Mapping

- Primary: none
- Secondary: none
