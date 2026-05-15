# Case 35: Calculate History Target With Explicit Entity

## Source Scenario

- Scenario: property owner が複数 entity にまたがるが、step metadata で target entity 自体は明示されている計算ケース
- Benchmark role: `calculate_target_resolution=history_target` を独立観測するための contrast case

## Target Meaning Elements

- `entity_resolution` と `calculate_target_resolution` の責務分離
- ambiguous owner 下でも explicit entity がある場合に current exact scope を property-side provenance へ反映できること
- natural-language only case と structured metadata case の境界

## Expected Structure Summary

- 注文を取得する
- `Total` を計算する
- 計算結果を表示する

## Expected IR

```json
{
  "case_id": "case_35_calculate_history_target_with_explicit_entity",
  "status": "draft",
  "module_name": "CalculateHistoryTargetWithExplicitEntity",
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
          "entity_resolution": "explicit_entity",
          "calculate_target_resolution": "history_target",
          "calculate_source_node_id": "step_1",
          "calculate_source_resolution": "input_link_var"
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
          "target_entity": "Item"
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

- property owner は `Order.Total` / `Invoice.Total` に分かれるため `schema_property` には上がらない
- ただし `target_entity=Order` が explicit metadata として与えられているので、property-side provenance は `history_target` まで上がってよい
- これは natural-language only の `history_fallback` case と区別して観測したい

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_35_calculate_history_target_with_explicit_entity.observed.json`
```

## Diff Notes

- 計算ノードは `intent=CALC`, `role=CALC`, `spec_role=CALCULATE` へ昇格した
- `semantic_roles.target_entity=Order` は explicit metadata として保持された
- owner ambiguity は残るため `entity_resolution` は `explicit_entity` に留まり、`schema_property` には上がらない
- その一方で property-side provenance は `calculate_target_resolution=history_target` となり、current exact scope があることを別 field で読める
- source 側は `calculate_source_resolution=input_link_var`, `calculate_source_node_id=step_1` を保持した

## Failure Mapping

- Primary: `None`
- Secondary: `None`
