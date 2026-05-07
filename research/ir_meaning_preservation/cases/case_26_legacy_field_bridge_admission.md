# Case 26: Legacy Field Bridge Admission

## Source Scenario

- Scenario: `Tier 2` の `legacy field bridge` が、owner explanation と canonical non-ambiguity を満たすとき canonicalization に使われることを確認したい
- Benchmark role: `schema_alias_coverage_policy` における `legacy field bridge` category の admission 検証

## Target Meaning Elements

- canonical `check_subject`
- canonical `property`
- `subject_resolution`
- `predicate_resolution`

## Expected Structure Summary

- 注文を取得する
- `伝票金額` が 100 より大きいか確認する
- 注文一覧を取得する
- `伝票金額` が 100 より大きい注文を抽出する

## Expected IR

```json
{
  "case_id": "case_26_legacy_field_bridge_admission",
  "status": "draft",
  "module_name": "LegacyFieldBridgeAdmission",
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
            "target_hint": "OrderAmount",
            "operator": "Greater",
            "expected_value": "100"
          }
        ],
        "semantic_roles": {
          "target_entity": "Order"
        },
        "spec_role": "CHECK",
        "check_kind": "comparison_check",
        "check_subject": "OrderAmount",
        "check_operator": ">",
        "check_value": "100",
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
            "target_hint": "OrderAmount",
            "operator": "Greater",
            "expected_value": "100"
          }
        ],
        "semantic_roles": {
          "target_entity": "Order",
          "property": "OrderAmount",
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

- `伝票金額 -> OrderAmount` は `legacy field bridge` とみなす
- category は `compound-part shorthand` と違っても、owner explanation と canonical non-ambiguity が揃えば admission 条件は同じはずである
- したがって `CHECK` / `FILTER` ともに `schema_property` まで上がることを期待する

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_26_legacy_field_bridge_admission.observed.json`
```

## Diff Notes

- `step_2` の `check_subject` は lexical token `伝票金額` ではなく canonical property `OrderAmount` に上がった
- `step_2.subject_resolution=schema_property` が保持され、`legacy field bridge` でも owner-confined な canonical property として admission されたことが確認できた
- `step_6` の `property` も canonical property `OrderAmount` に上がった
- `step_6.predicate_resolution=schema_property` が保持され、`FILTER` 側でも同じ admission が成立した
- したがって `legacy field bridge` は category 名に依らず、owner explanation と canonical non-ambiguity が揃えば `compound-part shorthand` と同じ条件で deterministic canonicalization に使ってよい

## Failure Mapping

- Primary: none
- Secondary: none
