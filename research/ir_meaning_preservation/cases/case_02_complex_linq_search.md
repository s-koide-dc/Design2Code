# Case 02: ComplexLinqSearch

## Source Scenario

- Scenario: `scenarios/ComplexLinqSearch.design.md`
- Benchmark role: JSON 読み込みと多段フィルタ連鎖の確認

## Target Meaning Elements

- file source の保持
- `FETCH -> JSON_DESERIALIZE -> LINQ -> LINQ -> DISPLAY` の依存連鎖
- `semantic_roles.property` の保持

## Expected Structure Summary

- `users.json` を読み込む
- JSON を `List<User>` に変換する
- `Name` 条件で絞り込む
- 前段結果を `Price` 条件でさらに絞り込む
- 結果を表示する

## Expected IR

```json
{
  "case_id": "case_02_complex_linq_search",
  "status": "draft",
  "module_name": "ComplexLinqSearch",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "User",
      "cardinality": "SINGLE",
      "output_type": "string",
      "source_kind": "file",
      "source_ref": "users.json",
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "FETCH",
          "path": "users.json"
        }
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_2",
      "type": "ACTION",
      "intent": "JSON_DESERIALIZE",
      "role": "TRANSFORM",
      "target_entity": "User",
      "cardinality": "COLLECTION",
      "output_type": "List<User>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "DESERIALIZE"
        }
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_3",
      "type": "ACTION",
      "intent": "LINQ",
      "role": "FILTER",
      "target_entity": "User",
      "cardinality": "COLLECTION",
      "output_type": "List<User>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_2",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "FILTER",
          "property": "Name"
        }
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_4",
      "type": "ACTION",
      "intent": "LINQ",
      "role": "FILTER",
      "target_entity": "User",
      "cardinality": "COLLECTION",
      "output_type": "List<User>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_3",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "FILTER",
          "property": "Price"
        }
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_5",
      "type": "ACTION",
      "intent": "DISPLAY",
      "role": "DISPLAY",
      "target_entity": "User",
      "cardinality": "COLLECTION",
      "output_type": "string",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_4",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "DISPLAY"
        }
      },
      "children": [],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- `step_1` は file source を持つ取得ノード
- `step_2` は `step_1` に依存する変換ノード
- `step_3` と `step_4` は直列フィルタとして接続する
- `step_5` は最終集合にのみ依存する
- `step_2` の `spec_role` は `DESERIALIZE`、`step_3` と `step_4` は `FILTER` として扱う

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_02_complex_linq_search.observed.json`
```

## Diff Notes

- 直列依存は保持されている
- `source_ref=users.json` が実 IR では落ちている
- `LINQ.role` は `FILTER` ではなく `ACTION`
- `DISPLAY.cardinality/output_type` が期待より弱い

## Failure Mapping

- Primary: `Source Drift`
- Secondary: `Intent Drift`
