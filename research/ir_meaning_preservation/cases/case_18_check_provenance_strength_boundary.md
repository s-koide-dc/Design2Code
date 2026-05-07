# Case 18: Check Provenance Strength Boundary

## Source Scenario

- Scenario: `CHECK` において、unique property owner による `schema_backed` 解決と、global には曖昧だが current target scope では決まる `history_based` 解決を同じケースで比較したい
- Benchmark role: `CHECK` の `subject_resolution` と exact-scope rule の境界観測

## Target Meaning Elements

- `spec_role=CHECK`
- `check_kind=comparison_check`
- `check_subject`
- `subject_resolution`

## Expected Structure Summary

- 商品を取得する
- 在庫が 0 より大きいか確認する
- 注文を取得する
- 合計金額が 100 より大きいか確認する

## Expected IR

```json
{
  "case_id": "case_18_check_provenance_strength_boundary",
  "status": "draft",
  "module_name": "CheckProvenanceStrengthBoundary",
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
            "target_hint": "Stock",
            "operator": "Greater",
            "expected_value": "0"
          }
        ],
        "semantic_roles": {
          "target_entity": "Product"
        },
        "spec_role": "CHECK",
        "check_kind": "comparison_check",
        "check_subject": "Stock",
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
      "target_entity": "Order",
      "cardinality": "SINGLE",
      "output_type": "Order",
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
      "id": "step_4",
      "type": "CONDITION",
      "intent": "EXISTS",
      "role": "CHECK",
      "target_entity": "Order",
      "cardinality": "SINGLE",
      "output_type": "bool",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_3",
      "semantic_map": {
        "logic": [
          {
            "type": "numeric",
            "target_hint": "Total",
            "operator": "Greater",
            "expected_value": "100"
          }
        ],
        "semantic_roles": {
          "target_entity": "Order"
        },
        "spec_role": "CHECK",
        "check_kind": "comparison_check",
        "check_subject": "Total",
        "check_operator": ">",
        "check_value": "100",
        "expected_truth": true,
        "subject_resolution": "history_subject"
      },
      "children": [],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- `step_2` の `Stock` は schema 上で `Product` に一意に属する property とみなし、`subject_resolution=schema_property`
- `step_4` の `Total` は global には複数 entity に属しうるため、schema-backed には上げず `history_subject`
- `step_4` は current target scope=`Order` を越えて別 entity の property を拾ってはならない
- 重要なのは `step_4` が unresolved ではなく、exact-scope に閉じた `history_based` 解決として保持されること

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_18_check_provenance_strength_boundary.observed.json`
```

## Diff Notes

- `step_2`, `step_6` ともに `comparison_check` 自体は保持された
- `step_2` は `在庫 -> Stock` に canonical 化され、`subject_resolution=schema_property` まで上がった
- `step_6` は `合計金額 -> Total` に canonical 化され、global には曖昧でも current scope=`Order` に閉じることで `subject_resolution=history_subject` に上がった
- これにより、`CHECK` でも property-side provenance が `schema_backed` と `history_based` に分離できることを観測できた
- then 側 `DISPLAY` の semantic continuity はまだ弱く、`semantic_roles.target_entity` は `Item` に留まる

## Failure Mapping

- Primary: none
- Secondary: none
