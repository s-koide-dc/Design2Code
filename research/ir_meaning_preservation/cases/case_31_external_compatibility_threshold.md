# Case 31: External Compatibility Threshold

## Source Scenario

- Scenario: 外部帳票語や legacy integration 名のように、実装都合ではなく外部制約により維持が必要な alias は `External Compatibility` により admission 候補へ上げるべきことを確認したい
- Benchmark role: `schema_alias_admission_threshold.md` の `External Compatibility` 閾値の検証

## Target Meaning Elements

- canonical `check_subject`
- canonical `property`
- `subject_resolution`
- `predicate_resolution`
- external-compatibility threshold interpretation

## Expected Structure Summary

- 請求書を取得する
- `請求金額` が 100 より大きいか確認する
- 請求書一覧を取得する
- `請求金額` が 100 より大きい請求書を抽出する

## Expected IR

```json
{
  "case_id": "case_31_external_compatibility_threshold",
  "status": "draft",
  "module_name": "ExternalCompatibilityThreshold",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "Invoice",
      "cardinality": "SINGLE",
      "output_type": "Invoice",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "Invoice"
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
      "target_entity": "Invoice",
      "cardinality": "SINGLE",
      "output_type": "bool",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1",
      "semantic_map": {
        "logic": [
          {
            "type": "numeric",
            "target_hint": "InvoiceAmount",
            "operator": "Greater",
            "expected_value": "100"
          }
        ],
        "semantic_roles": {
          "target_entity": "Invoice"
        },
        "spec_role": "CHECK",
        "check_kind": "comparison_check",
        "check_subject": "InvoiceAmount",
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
      "target_entity": "Invoice",
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<Invoice>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_2",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "Invoice"
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
      "target_entity": "Invoice",
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<Invoice>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_3",
      "semantic_map": {
        "logic": [
          {
            "type": "numeric",
            "target_hint": "InvoiceAmount",
            "operator": "Greater",
            "expected_value": "100"
          }
        ],
        "semantic_roles": {
          "target_entity": "Invoice",
          "property": "InvoiceAmount",
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

- `請求金額 -> InvoiceAmount` は external form や帳票語との互換を保つための alias とみなす
- repeated-use や cross-case 再出だけでなく、外部互換要件そのものが admission 根拠になる想定である
- したがって canonical property への昇格を期待する

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_31_external_compatibility_threshold.observed.json`
```

## Diff Notes

- `step_2` の `check_subject` は canonical property `InvoiceAmount` に上がった
- `step_2.subject_resolution=schema_property` が保持され、帳票語/外部連携語としての compatibility 要件を admission timing の根拠にしても canonical path が成立することが確認できた
- `step_6` の `property` も canonical property `InvoiceAmount` に上がった
- `step_6.predicate_resolution=schema_property` が保持され、`FILTER` 側でも同じ admission が成立した
- したがって `External Compatibility` は repeated-use や downstream impact と独立した schema admission 根拠として扱ってよい

## Failure Mapping

- Primary: none
- Secondary: none
