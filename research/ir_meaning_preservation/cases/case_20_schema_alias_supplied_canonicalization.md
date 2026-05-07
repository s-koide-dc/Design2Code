# Case 20: Schema Alias Supplied Canonicalization

## Source Scenario

- Scenario: schema に explicit alias がある前提で、lexical property token が canonical property へ deterministic に写ることを確認したい
- Benchmark role: alias supply model と property-side provenance promotion の結合確認

## Target Meaning Elements

- `CHECK.subject_resolution`
- `FILTER.predicate_resolution`
- canonical `check_subject` / `property`

## Expected Structure Summary

- 商品を取得する
- `在庫` が 0 より大きいか確認する
- 商品一覧を取得する
- `在庫` が 0 より大きい商品を抽出する

## Expected IR

```json
{
  "case_id": "case_20_schema_alias_supplied_canonicalization",
  "status": "draft",
  "module_name": "SchemaAliasSuppliedCanonicalization",
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
    }
  ]
}
```

## Expected Node Notes

- schema alias `在庫 -> Stock` が明示されていることを前提にする
- `CHECK` も `FILTER` も lexical token ではなく canonical property `Stock` を保持する
- これは promotion success であると同時に supply success でもある

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_20_schema_alias_supplied_canonicalization.observed.json`
```

## Diff Notes

- `step_2` の `check_subject` は `在庫` ではなく canonical property `Stock` に上がった
- `step_2.subject_resolution=schema_property` が保持された
- `step_6` の `property` も `在庫` ではなく canonical property `Stock` に上がった
- `step_6.predicate_resolution=schema_property` が保持された
- したがって alias supply がある場合、`CHECK` / `FILTER` の両方で deterministic canonicalization と property-side provenance promotion が成立する
- `target_entity=Product` と `collection_resolution=explicit_input_link` も保持されており、supply success と promotion success を分けずに読める

## Failure Mapping

- Primary: none
- Secondary: none
