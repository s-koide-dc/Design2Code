# Case 29: Cross-Case Relevance Threshold

## Source Scenario

- Scenario: 同じ lexical token が複数 benchmark で canonicalization failure の原因として再出する場合、`Cross-Case Relevance` により admission 候補へ上げるべきことを確認したい
- Benchmark role: `schema_alias_admission_threshold.md` の `Cross-Case Relevance` 閾値の検証

## Target Meaning Elements

- canonical `check_subject`
- canonical `property`
- `subject_resolution`
- `predicate_resolution`
- cross-case threshold interpretation

## Expected Structure Summary

- 注文を取得する
- `受注区分` が 1 より大きいか確認する
- 注文一覧を取得する
- `受注区分` が 1 より大きい注文を抽出する

## Expected IR

```json
{
  "case_id": "case_29_cross_case_relevance_threshold",
  "status": "draft",
  "module_name": "CrossCaseRelevanceThreshold",
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

- `受注区分 -> OrderCategory` は `case_27` / `case_28` に続いて再出する lexical token なので、`Cross-Case Relevance` により admission 候補へ上がる
- このケース単体で repeated-use を持たなくても、benchmark 横断の再出現が admission 根拠になる想定である
- したがって canonical property への昇格を期待する

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_29_cross_case_relevance_threshold.observed.json`
```

## Diff Notes

- `step_2` の `check_subject` は canonical property `OrderCategory` に上がった
- `step_2.subject_resolution=schema_property` が保持され、cross-case relevance を admission timing の根拠として扱っても canonical path が崩れないことが確認できた
- `step_6` の `property` も canonical property `OrderCategory` に上がった
- `step_6.predicate_resolution=schema_property` が保持され、`FILTER` 側でも同じ admission が成立した
- したがって repeated-use 単独でなくても、benchmark 横断での再出現を schema admission 根拠として扱う整理は妥当である

## Failure Mapping

- Primary: none
- Secondary: none
