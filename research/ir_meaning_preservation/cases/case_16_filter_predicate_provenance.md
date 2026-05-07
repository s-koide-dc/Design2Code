# Case 16: Filter Predicate Provenance

## Source Scenario

- Scenario: filter 条件はあるが、その predicate が explicit ops 由来なのか logic goal 由来なのかを見分けたいケース
- Benchmark role: `FILTER` に対する `predicate_resolution` / `collection_resolution` の観測

## Target Meaning Elements

- `spec_role=FILTER`
- `semantic_roles.property`
- `semantic_roles.predicate_resolution`
- `semantic_roles.collection_resolution`

## Expected Structure Summary

- ユーザー一覧を取得する
- `Points > input` で絞り込む
- 結果を表示する

## Expected IR

```json
{
  "case_id": "case_16_filter_predicate_provenance",
  "status": "draft",
  "module_name": "FilterPredicateProvenance",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "User",
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<User>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "User"
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
      "target_entity": "User",
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<User>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1",
      "semantic_map": {
        "logic": [
          {
            "type": "numeric",
            "target_hint": "Points",
            "operator": "Greater",
            "expected_value": "input_1"
          }
        ],
        "semantic_roles": {
          "target_entity": "User",
          "property": "Points",
          "predicate_resolution": "logic_goal",
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
      "intent": "DISPLAY",
      "role": "DISPLAY",
      "target_entity": "User",
      "cardinality": "COLLECTION",
      "output_type": "string",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_2",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "target_entity": "User"
        },
        "spec_role": "DISPLAY"
      },
      "children": [],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- predicate が logic goal から構成されるなら `predicate_resolution=logic_goal`
- collection source が前段 `FETCH` の明示リンクで決まるなら `collection_resolution=explicit_input_link`
- explicit `ops` しかない場合は `predicate_resolution=explicit_ops` との比較対象に使う
- このケース自体は `logic_goal` 由来を基準形として固定する
- `property=Points` は downstream の `.Where(x => x.Points > input_1)` 具体化に使える強い predicate とみなす

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_16_filter_predicate_provenance.observed.json`
```

## Diff Notes

- `step_2` は期待どおり `LINQ/FILTER` に上がった
- `semantic_roles.property=Points` が保持された
- `predicate_resolution=logic_goal` と `collection_resolution=explicit_input_link` も保持された
- `input_link=step_1` は collection provenance の基礎事実として期待どおり残っている

## Failure Mapping

- Primary: none
- Secondary: none
