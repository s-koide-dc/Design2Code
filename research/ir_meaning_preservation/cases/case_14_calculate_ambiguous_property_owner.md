# Case 14: Calculate Ambiguous Property Owner

## Source Scenario

- Scenario: 複数 entity が同じ property 名を持つ schema 上での計算ケース
- Benchmark role: ambiguous property owner を持つ `CALCULATE`

## Target Meaning Elements

- `CALCULATE` 昇格と `target_entity` 補正の分離
- property owner が一意でないときの ambiguity preserve
- `semantic_roles.property` は保持しつつ entity を誤補正しないこと

## Expected Structure Summary

- レコードを取得する
- `Total` を計算する
- 計算結果を表示する

## Expected IR

```json
{
  "case_id": "case_14_calculate_ambiguous_property_owner",
  "status": "draft",
  "module_name": "CalculateAmbiguousPropertyOwner",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "Item",
      "cardinality": "SINGLE",
      "output_type": null,
      "source_kind": "memory",
      "source_ref": null,
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "Item"
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
      "target_entity": "Item",
      "cardinality": "SINGLE",
      "output_type": null,
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "Item",
          "target_hint": "Total",
          "property": "Total",
          "entity_resolution": "ambiguous"
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
      "target_entity": "Item",
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

- 計算ノードは `CALC/CALCULATE` へ昇格してよい
- ただし `Order.Total` と `Invoice.Total` の両方が schema 上にあるなら、`target_entity` は特定 entity に補正しない
- ambiguity preserve が成立していれば、このケースでは weak entity 維持が正しい

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_14_calculate_ambiguous_property_owner.observed.json`
```

## Diff Notes

- 計算ノードは `intent=CALC`, `role=CALC`, `spec_role=CALCULATE` へ昇格した
- `semantic_roles.target_hint=Total` と `property=Total` は保持された
- `entity_resolution=ambiguous` が付き、曖昧性保存であることが IR 上で読める
- ただし `Order.Total` と `Invoice.Total` の owner ambiguity があるため、`target_entity` は `Item` のまま維持された
- 表示ノードも同じ weak entity を引き継いでおり、ambiguous owner を安易に解消していない
- この観測は `calculate_target_entity_ambiguity_rule.md` の Rule D と整合する

## Failure Mapping

- Primary: `None`
- Secondary: `None`
