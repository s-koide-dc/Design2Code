# Case 12: Calculate With Target Hint

## Source Scenario

- Scenario: `StateUpdatePersist.design.md` と計算系 service ステップを抽象化したケース
- Benchmark role: explicit target hint を持つ `CALCULATE`

## Target Meaning Elements

- 計算対象 property の明示
- `CALCULATE` と一般 `TRANSFORM` の境界
- upstream detection と downstream bridge の接続

## Expected Structure Summary

- 商品を取得する
- `DiscountedPrice` を計算する
- 計算結果を表示する

## Expected IR

```json
{
  "case_id": "case_12_calculate_with_target_hint",
  "status": "draft",
  "module_name": "CalculateWithTargetHint",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "Product",
      "cardinality": "SINGLE",
      "output_type": "Product",
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
      "type": "ACTION",
      "intent": "CALC",
      "role": "CALC",
      "target_entity": "Product",
      "cardinality": "SINGLE",
      "output_type": "decimal",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1",
      "semantic_map": {
        "logic": [
          {
            "type": "calculation",
            "target_hint": "DiscountedPrice",
            "variable_hint": "DiscountedPrice"
          }
        ],
        "semantic_roles": {
          "spec_role": "CALCULATE",
          "target_hint": "DiscountedPrice",
          "property": "DiscountedPrice",
          "entity_resolution": "unique_owner"
        }
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_3",
      "type": "ACTION",
      "intent": "DISPLAY",
      "role": "DISPLAY",
      "target_entity": "Product",
      "cardinality": "SINGLE",
      "output_type": "string",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_2",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "DISPLAY",
          "property": "DiscountedPrice"
        }
      },
      "children": [],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- 計算ノードは `intent=CALC`, `role=CALC`, `spec_role=CALCULATE`
- `semantic_roles.target_hint` または同等の計算対象が保持される
- 表示ノードは計算ノードへ依存する

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_12_calculate_with_target_hint.observed.json`
```

## Diff Notes

- `semantic_roles.target_hint=DiscountedPrice` と `property=DiscountedPrice` は保持された
- 計算ノードは `intent=CALC`, `role=CALC`, `spec_role=CALCULATE` へ昇格した
- schema 上で owner が一意に決まる場合は `entity_resolution=unique_owner` が付く
- explicit target hint は metadata だけでなく、`CALCULATE` 昇格規則の入力として機能した
- 表示ノードの `input_link = step_2` は保持された

## Failure Mapping

- Primary: `Under-Spec Capture`
- Secondary: `None`
