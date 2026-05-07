# Case 09: Condition Branch Dependency

## Source Scenario

- Scenario: `RobustConfigLoader.design.md` を拡張した分岐依存観察ケース
- Benchmark role: `CONDITION` 配下の `first-child` / `second sibling`

## Target Meaning Elements

- then 側 first-child の条件親依存
- then 側 second sibling の逐次 sibling 依存
- else 側 first-child の条件親依存

## Expected Structure Summary

- 条件を判定する
- then 側では first-child でデータを取得し、その結果を次ノードで表示する
- else 側では first-child でエラーメッセージを表示する

## Expected IR

```json
{
  "case_id": "case_09_condition_branch_dependency",
  "status": "draft",
  "module_name": "ConditionBranchDependency",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "CONDITION",
      "intent": "EXISTS",
      "role": "CHECK",
      "target_entity": "Config",
      "cardinality": "SINGLE",
      "output_type": "bool",
      "source_kind": "file",
      "source_ref": "config.json",
      "input_link": null,
      "condition_expression": "config.json exists",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "CHECK",
          "path": "config.json"
        }
      },
      "children": [
        {
          "id": "step_2",
          "type": "ACTION",
          "intent": "FETCH",
          "role": "FETCH",
          "target_entity": "Config",
          "cardinality": "SINGLE",
          "output_type": "Config",
          "source_kind": "file",
          "source_ref": "config.json",
          "input_link": "step_1",
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "spec_role": "FETCH",
              "path": "config.json"
            }
          },
          "children": [],
          "else_children": []
        },
        {
          "id": "step_3",
          "type": "ACTION",
          "intent": "DISPLAY",
          "role": "DISPLAY",
          "target_entity": "Config",
          "cardinality": "SINGLE",
          "output_type": "string",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": "step_2",
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "spec_role": "DISPLAY",
              "property": "Summary"
            }
          },
          "children": [],
          "else_children": []
        }
      ],
      "else_children": [
        {
          "id": "step_4",
          "type": "ACTION",
          "intent": "DISPLAY",
          "role": "DISPLAY",
          "target_entity": "string",
          "cardinality": "SINGLE",
          "output_type": "string",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": "step_1",
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "spec_role": "DISPLAY",
              "message": "config.json not found"
            }
          },
          "children": [],
          "else_children": []
        }
      ]
    }
  ]
}
```

## Expected Node Notes

- then 側最初のノードは `input_link = condition`
- then 側 2 個目のノードは `input_link = then_first_child`
- else 側最初のノードは `input_link = condition`
- then 側と else 側の dependency base を混同しない

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_09_condition_branch_dependency.observed.json`
```

## Diff Notes

- then 側 first-child は期待どおり `input_link = step_1`
- then 側 second sibling も期待どおり `input_link = step_2`
- else 側 first-child も `input_link = step_1` に戻り、then/else の dependency base 混同は解消した
- 一方で `target_entity`, `source_kind`, `source_ref`, `check_subject` は期待より弱い

## Failure Mapping

- Primary: `Under-Spec Capture`
- Secondary: `None`
