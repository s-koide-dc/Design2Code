# Case 23: Disallowed Generic Alias Rejection

## Source Scenario

- Scenario: coverage policy 上で拒否される generic alias が、canonicalization されず weak retention に留まることを確認したい
- Benchmark role: `schema_alias_coverage_policy` の rejection 側の検証

## Target Meaning Elements

- lexical `check_subject`
- lexical `property`
- `subject_resolution`
- `predicate_resolution`

## Expected Structure Summary

- 注文を取得する
- `金額` が 100 より大きいか確認する
- 注文一覧を取得する
- `金額` が 100 より大きい注文を抽出する

## Expected IR

```json
{
  "case_id": "case_23_disallowed_generic_alias_rejection",
  "status": "draft",
  "module_name": "DisallowedGenericAliasRejection",
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
            "target_hint": null,
            "operator": "Greater",
            "expected_value": "100"
          }
        ],
        "semantic_roles": {
          "target_entity": "Order"
        },
        "spec_role": "CHECK",
        "check_kind": "comparison_check",
        "check_subject": "金額",
        "check_operator": ">",
        "check_value": "100",
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
            "target_hint": null,
            "operator": "Greater",
            "expected_value": "100"
          }
        ],
        "semantic_roles": {
          "target_entity": "Order",
          "property": "金額",
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

- `金額` は policy 上の disallowed generic alias とみなす
- したがって canonical property `Total` へ上げてはならない
- `CHECK` は `explicit_subject`、`FILTER` は `logic_goal` に留まるのが正しい

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_23_disallowed_generic_alias_rejection.observed.json`
```

## Diff Notes

- `step_2` の `check_subject` は lexical token `金額` のまま保持された
- `step_2.subject_resolution` は `explicit_subject` に留まり、generic token は canonical property `Total` へ誤上昇していない
- `step_6` の `property` も lexical token `金額` のまま保持された
- `step_6.predicate_resolution` は `logic_goal` に留まり、coverage policy の rejection と整合している
- したがって alias supply が存在していても、admission されない generic token は weak retention に留まることが confirmed できた

## Failure Mapping

- Primary: none
- Secondary: none
