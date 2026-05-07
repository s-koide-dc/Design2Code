# Case 19: Filter Provenance Strength Boundary

## Source Scenario

- Scenario: `FILTER` において、unique property owner による `schema_backed` 解決と、global には曖昧だが current collection scope では決まる `history_based` 解決を同じケースで比較したい
- Benchmark role: `FILTER` の `predicate_resolution` と exact-scope rule の境界観測

## Target Meaning Elements

- `spec_role=FILTER`
- `semantic_roles.property`
- `predicate_resolution`
- `collection_resolution`

## Expected Structure Summary

- 商品一覧を取得する
- 在庫が 0 より大きい商品を抽出する
- 注文一覧を取得する
- 合計金額が 100 より大きい注文を抽出する

## Expected IR

```json
{
  "case_id": "case_19_filter_provenance_strength_boundary",
  "status": "draft",
  "module_name": "FilterProvenanceStrengthBoundary",
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
          "target_entity": "Product"
        },
        "spec_role": "FETCH"
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_2",
      "type": "ACTION",
      "intent": "LINQ",
      "role": "FILTER",
      "target_entity": "Product",
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<Product>",
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
          "target_entity": "Product",
          "property": "Stock",
          "predicate_resolution": "schema_property",
          "collection_resolution": "explicit_input_link"
        },
        "spec_role": "FILTER"
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
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<Order>",
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
      "type": "ACTION",
      "intent": "LINQ",
      "role": "FILTER",
      "target_entity": "Order",
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<Order>",
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
          "target_entity": "Order",
          "property": "Total",
          "predicate_resolution": "history_predicate",
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

- `step_2` の `Stock` は `Product` に一意に属する property とみなし、`predicate_resolution=schema_property`
- `step_4` の `Total` は global schema だけでは一意に決まらないため、`history_predicate` に留める
- `step_4` は current collection scope=`Order` に閉じた解決であり、別 collection/entity へ滑ってはならない
- どちらも `collection_resolution=explicit_input_link` だが、predicate 側の強度差が評価対象である

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_19_filter_provenance_strength_boundary.observed.json`
```

## Diff Notes

- `step_2`, `step_4` ともに `LINQ/FILTER` には上がった
- `step_2` は `在庫 -> Stock` に canonical 化され、`predicate_resolution=schema_property` まで上がった
- `step_4` は `合計金額 -> Total` に canonical 化され、global には曖昧でも current collection scope=`Order` に閉じることで `predicate_resolution=history_predicate` に上がった
- `collection_resolution=explicit_input_link` は両方で維持されており、collection provenance と property provenance の両方を同時に保持できている
- これにより、`FILTER` でも property-side provenance が `schema_backed` と `history_based` に分離できることを観測できた

## Failure Mapping

- Primary: none
- Secondary: none
