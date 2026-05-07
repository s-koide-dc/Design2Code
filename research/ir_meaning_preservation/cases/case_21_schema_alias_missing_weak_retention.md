# Case 21: Schema Alias Missing Weak Retention

## Source Scenario

- Scenario: lexical property token はあるが schema alias が供給されていない場合に、無理な canonicalization が起きないことを確認したい
- Benchmark role: alias supply failure と provenance promotion failure の切り分け

## Target Meaning Elements

- `CHECK.subject_resolution`
- `FILTER.predicate_resolution`
- lexical `check_subject` / `property`

## Expected Structure Summary

- 商品を取得する
- `在庫` が 0 より大きいか確認する
- 商品一覧を取得する
- `在庫` が 0 より大きい商品を抽出する

## Expected IR

```json
{
  "case_id": "case_21_schema_alias_missing_weak_retention",
  "status": "draft",
  "module_name": "SchemaAliasMissingWeakRetention",
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
            "target_hint": null,
            "operator": "Greater",
            "expected_value": "0"
          }
        ],
        "semantic_roles": {
          "target_entity": "Product"
        },
        "spec_role": "CHECK",
        "check_kind": "comparison_check",
        "check_subject": "在庫",
        "check_operator": ">",
        "check_value": "0",
        "expected_truth": true,
        "subject_resolution": "explicit_subject"
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
            "target_hint": null,
            "operator": "Greater",
            "expected_value": "0"
          }
        ],
        "semantic_roles": {
          "target_entity": "Product",
          "property": "在庫",
          "predicate_resolution": "logic_goal",
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

- schema に alias が無い前提なので、`在庫 -> Stock` のような canonicalization は起こしてはならない
- `CHECK` は `explicit_subject` に留まり、`FILTER` は `logic_goal` に留まる
- これは promotion failure ではなく supply failure として読む

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_21_schema_alias_missing_weak_retention.observed.json`
```

## Diff Notes

- `step_2` の `check_subject` は lexical token `在庫` のまま保持された
- `step_2.subject_resolution` は `explicit_subject` に留まり、無理な canonicalization は起きていない
- `step_6` の `property` も lexical token `在庫` のまま保持された
- `step_6.predicate_resolution` は `logic_goal` に留まり、`schema_property` へ誤昇格していない
- したがって alias supply が無い場合、現在実装は weak retention に留まり、supply failure を promotion failure と混同していない
- `FILTER` への昇格自体は維持されているため、弱いのは role ではなく property canonicalization 側である

## Failure Mapping

- Primary: none
- Secondary: none
