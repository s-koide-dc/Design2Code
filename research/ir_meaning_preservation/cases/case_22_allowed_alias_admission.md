# Case 22: Allowed Alias Admission

## Source Scenario

- Scenario: coverage policy 上で許可される alias が、canonicalization に正しく使われることを確認したい
- Benchmark role: `schema_alias_coverage_policy` の admission 側の検証

## Target Meaning Elements

- canonical `check_subject`
- canonical `property`
- `subject_resolution`
- `predicate_resolution`

## Expected Structure Summary

- 注文を取得する
- `合計金額` が 100 より大きいか確認する
- 注文一覧を取得する
- `合計金額` が 100 より大きい注文を抽出する

## Expected IR

```json
{
  "case_id": "case_22_allowed_alias_admission",
  "status": "draft",
  "module_name": "AllowedAliasAdmission",
  "logic_tree": [
    {
      "id": "step_1",
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
      "id": "step_2",
      "type": "CONDITION",
      "intent": "EXISTS",
      "role": "CHECK",
      "target_entity": "Order",
      "cardinality": "SINGLE",
      "output_type": "bool",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1",
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
      "input_link": "step_2",
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

- `合計金額 -> Total` は policy 上の allowed alias とみなす
- `Total` 自体は複数 owner を持ちうるため、`CHECK` / `FILTER` ともに `history_*` へ上がる
- 重要なのは `allowed alias` であっても、必ずしも `schema_property` になるわけではない点である

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_22_allowed_alias_admission.observed.json`
```

## Diff Notes

- `step_2` の `check_subject` は lexical token `合計金額` ではなく canonical property `Total` に上がった
- `step_2.subject_resolution=history_subject` が保持され、allowed alias admission と owner ambiguity の分離が見える形になった
- `step_6` の `property` も canonical property `Total` に上がった
- `step_6.predicate_resolution=history_predicate` が保持され、`FILTER` 側でも同じ admission が成立した
- `schema_property` ではなく `history_*` に留まっている点は expected と整合しており、coverage admission は owner uniqueness を意味しないことが確認できた

## Failure Mapping

- Primary: none
- Secondary: none
