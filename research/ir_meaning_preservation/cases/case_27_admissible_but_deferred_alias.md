# Case 27: Admissible But Deferred Alias

## Source Scenario

- Scenario: owner-confined かつ deterministic だが、benchmark need がまだ弱い alias は `Hold For Evidence` に置くべきことを確認したい
- Benchmark role: `schema_alias_admission_threshold.md` の `admissible but deferred` 状態の検証

## Target Meaning Elements

- lexical `check_subject`
- lexical `property`
- `subject_resolution`
- `predicate_resolution`
- alias state interpretation

## Expected Structure Summary

- 注文を取得する
- `受注区分` が 1 より大きいか確認する
- 注文一覧を取得する
- `受注区分` が 1 より大きい注文を抽出する

## Expected IR

```json
{
  "case_id": "case_27_admissible_but_deferred_alias",
  "status": "draft",
  "module_name": "AdmissibleButDeferredAlias",
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
            "expected_value": "1"
          }
        ],
        "semantic_roles": {
          "target_entity": "Order"
        },
        "spec_role": "CHECK",
        "check_kind": "comparison_check",
        "check_subject": "受注区分",
        "check_operator": ">",
        "check_value": "1",
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
            "expected_value": "1"
          }
        ],
        "semantic_roles": {
          "target_entity": "Order",
          "property": "受注区分",
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

- `受注区分 -> OrderCategory` のような alias は owner-confined かもしれないが、このケース単独では benchmark need が弱いとみなす
- したがって policy 上は `can_admit=true` でも `should_admit_now=false` であり、IR 上は lexical retention に留める
- このケースは rejection ではなく deferred hold の観測基準である

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_27_admissible_but_deferred_alias.observed.json`
```

## Diff Notes

- `step_2` の `check_subject` は lexical token `受注区分` のまま保持された
- `step_2.subject_resolution` は `explicit_subject` に留まり、schema に未 admission の alias は lexical retention に留まることが確認できた
- `step_6` の `property` も lexical token `受注区分` のまま保持された
- `step_6.predicate_resolution` は `logic_goal` に留まり、このケースが rejection ではなく deferred hold として読める
- したがって `can_admit=true` でも `should_admit_now=false` の間は、runtime 挙動ではなく schema admission を保留する方針で十分である

## Failure Mapping

- Primary: none
- Secondary: none
