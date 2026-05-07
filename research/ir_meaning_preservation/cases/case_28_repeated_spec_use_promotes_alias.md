# Case 28: Repeated Spec Use Promotes Alias

## Source Scenario

- Scenario: 同じ owner context で同一 lexical token が反復使用されると、`Hold For Evidence` だった alias が `Admit Now` へ上がる基準を確認したい
- Benchmark role: `schema_alias_admission_threshold.md` の `Repeated Spec Use` 閾値の検証

## Target Meaning Elements

- canonical `check_subject`
- canonical `property`
- `subject_resolution`
- `predicate_resolution`
- repeated-use threshold interpretation

## Expected Structure Summary

- 注文を取得する
- `受注区分` が 1 より大きいか確認する
- `受注区分` を表示する
- 注文一覧を取得する
- `受注区分` が 1 より大きい注文を抽出する

## Expected IR

```json
{
  "case_id": "case_28_repeated_spec_use_promotes_alias",
  "status": "draft",
  "module_name": "RepeatedSpecUsePromotesAlias",
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
            "target_hint": "OrderCategory",
            "operator": "Greater",
            "expected_value": "1"
          }
        ],
        "semantic_roles": {
          "target_entity": "Order"
        },
        "spec_role": "CHECK",
        "check_kind": "comparison_check",
        "check_subject": "OrderCategory",
        "check_operator": ">",
        "check_value": "1",
        "expected_truth": true,
        "subject_resolution": "schema_property"
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
          "target_entity": "Order"
        },
        "spec_role": "DISPLAY"
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_4",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "Order",
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<Order>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_3",
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
      "id": "step_5",
      "type": "ACTION",
      "intent": "LINQ",
      "role": "FILTER",
      "target_entity": "Order",
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<Order>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_4",
      "semantic_map": {
        "logic": [
          {
            "type": "numeric",
            "target_hint": "OrderCategory",
            "operator": "Greater",
            "expected_value": "1"
          }
        ],
        "semantic_roles": {
          "target_entity": "Order",
          "property": "OrderCategory",
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

- `受注区分 -> OrderCategory` を repeated-use で `Admit Now` に上げる想定である
- `DISPLAY` を挟むことで、単発比較ではなく同一 owner context で lexical token が反復使用される状況を作る
- 期待は canonical property への昇格だが、これは policy threshold を benchmark で満たしたとみなす場合に限る

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_28_repeated_spec_use_promotes_alias.observed.json`
```

## Diff Notes

- `step_2` の `check_subject` は canonical property `OrderCategory` に上がった
- `step_2.subject_resolution=schema_property` が保持され、repeated-use を満たして schema admission された後の expected path が確認できた
- `step_6` の `property` も canonical property `OrderCategory` に上がった
- `step_6.predicate_resolution=schema_property` が保持され、`FILTER` 側でも同じ admission path が成立した
- したがって threshold を超えて schema に入った alias は、通常の admitted alias と同じ deterministic canonicalization 経路でよい

## Failure Mapping

- Primary: none
- Secondary: none
