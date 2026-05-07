# Case 30: Downstream Impact Threshold

## Source Scenario

- Scenario: lexical retention のままだと downstream conservatism により生成が止まり、研究比較にも影響する alias は `Downstream Impact` により admission 候補へ上げるべきことを確認したい
- Benchmark role: `schema_alias_admission_threshold.md` の `Downstream Impact` 閾値の検証

## Target Meaning Elements

- canonical `check_subject`
- canonical `property`
- `subject_resolution`
- `predicate_resolution`
- downstream-impact threshold interpretation

## Expected Structure Summary

- 商品を取得する
- `棚卸数量` が 0 より大きいか確認する
- 商品一覧を取得する
- `棚卸数量` が 0 より大きい商品を抽出する

## Expected IR

```json
{
  "case_id": "case_30_downstream_impact_threshold",
  "status": "draft",
  "module_name": "DownstreamImpactThreshold",
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
          "target_entity": "Product"
        },
        "spec_role": "FETCH"
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_2",
      "type": "CONDITION",
      "intent": "EXISTS",
      "role": "CHECK",
      "target_entity": "Product",
      "cardinality": "SINGLE",
      "output_type": "bool",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1",
      "semantic_map": {
        "logic": [
          {
            "type": "numeric",
            "target_hint": "InventoryCount",
            "operator": "Greater",
            "expected_value": "0"
          }
        ],
        "semantic_roles": {
          "target_entity": "Product"
        },
        "spec_role": "CHECK",
        "check_kind": "comparison_check",
        "check_subject": "InventoryCount",
        "check_operator": ">",
        "check_value": "0",
        "expected_truth": true,
        "subject_resolution": "schema_property"
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_3",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "Product",
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<Product>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_2",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "Product"
        },
        "spec_role": "FETCH"
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_4",
      "type": "ACTION",
      "intent": "LINQ",
      "role": "FILTER",
      "target_entity": "Product",
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<Product>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_3",
      "semantic_map": {
        "logic": [
          {
            "type": "numeric",
            "target_hint": "InventoryCount",
            "operator": "Greater",
            "expected_value": "0"
          }
        ],
        "semantic_roles": {
          "target_entity": "Product",
          "property": "InventoryCount",
          "predicate_resolution": "schema_property",
          "collection_resolution": "explicit_input_link"
        },
        "spec_role": "FILTER"
      },
      "children": [],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- `棚卸数量 -> InventoryCount` は lexical retention のままだと downstream comparison/filter generation を weak path に押しやすい alias とみなす
- したがって `Downstream Impact` を admission 根拠として canonical property へ上げる想定である
- repeated-use や cross-case 再出とは別に、downstream conservatism への影響を admission timing の根拠として扱う

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_30_downstream_impact_threshold.observed.json`
```

## Diff Notes

- `step_2` の `check_subject` は canonical property `InventoryCount` に上がった
- `step_2.subject_resolution=schema_property` が保持され、downstream comparison generation へ渡すための canonicalization として十分読める
- `step_6` の `property` も canonical property `InventoryCount` に上がった
- `step_6.predicate_resolution=schema_property` が保持され、`FILTER` 側でも weak path を避ける admission として機能している
- したがって `Downstream Impact` を admission timing の根拠として使う整理は、runtime semantics を壊さずに成立する

## Failure Mapping

- Primary: none
- Secondary: none
