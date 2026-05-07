# Case 06: Check Exists File

## Source Scenario

- Scenario: `scenarios/RobustConfigLoader.design.md` の条件判定部分を単独抽出
- Benchmark role: `exists_check` の最小ケース

## Target Meaning Elements

- file source を伴う存在確認
- `CHECK` と `FETCH` の境界
- 条件ノード上での `check_kind` 保持

## Expected Structure Summary

- `config.json` が存在するかを確認する
- true の場合は設定を読み込む
- false の場合は not found を表示する

## Expected IR

```json
{
  "case_id": "case_06_check_exists_file",
  "status": "draft",
  "module_name": "CheckExistsFile",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "CONDITION",
      "intent": "EXISTS",
      "role": "CHECK",
      "target_entity": "string",
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
        },
        "check_kind": "exists_check",
        "check_subject": "config.json",
        "expected_truth": true,
        "source_ref": "config.json",
        "source_kind": "file"
      },
      "children": [
        {
          "id": "step_2",
          "type": "ACTION",
          "intent": "FETCH",
          "role": "FETCH",
          "target_entity": "string",
          "cardinality": "SINGLE",
          "output_type": "string",
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
        }
      ],
      "else_children": [
        {
          "id": "step_3",
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

- `step_1` は `exists_check` を持つ `CONDITION`
- `source_ref/source_kind` は条件ノード側でも保持する
- `step_2` は判定そのものではなく、判定通過後の `FETCH`
- `step_3` は false 分岐の通知

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_06_check_exists_file.observed.json`
```

## Diff Notes

- `check_kind=exists_check` は期待どおり保持された
- `source_ref=config.json` と `source_kind=file` も `semantic_map` に保持された
- `target_entity` は期待の `string` ではなく `Item`
- false 分岐ノードは `step_3` ではなく `step_4` に対応している
- 生成条件式は `File.Exists("config.json")` となり、期待と整合した

## Failure Mapping

- Primary: `Under-Spec Capture`
- Secondary: `None`
