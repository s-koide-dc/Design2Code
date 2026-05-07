# Case 01: StdinToStdoutTransform

## Source Scenario

- Scenario: `scenarios/StdinToStdoutTransform.design.md`
- Benchmark role: 最小の直列変換ケース

## Target Meaning Elements

- source_kind=`stdin`
- `FETCH -> TRANSFORM -> DISPLAY` の直列依存
- `ops:trim_upper` の意味保持

## Expected Structure Summary

- 標準入力から 1 行取得する
- 取得文字列をトリムし、大文字化する
- 変換結果を表示する

## Expected IR

```json
{
  "case_id": "case_01_stdin_to_stdout_transform",
  "status": "draft",
  "module_name": "StdinToStdoutTransform",
  "logic_tree": [
    {
      "id": "step_2",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "string",
      "cardinality": "SINGLE",
      "output_type": "string",
      "source_kind": "stdin",
      "source_ref": "STDIN",
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "FETCH",
          "name": "STDIN"
        }
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_3",
      "type": "ACTION",
      "intent": "TRANSFORM",
      "role": "TRANSFORM",
      "target_entity": "string",
      "cardinality": "SINGLE",
      "output_type": "string",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_2",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "TRANSFORM",
          "ops": [
            "trim_upper"
          ]
        }
      },
      "children": [],
      "else_children": []
    },
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
      "input_link": "step_3",
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

- `step_2` は `FETCH` 系ノードとして扱う
- `step_3` は `TRANSFORM` 系ノードとして扱う
- `step_4` は `DISPLAY` 系ノードとして扱う
- 各ノードの `semantic_map.semantic_roles.spec_role` を意味保存評価の基準とする

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_01_stdin_to_stdout_transform.observed.json`
```

## Diff Notes

- 構造自体は一致している
- `id` が期待より 1 つ前倒しで始まっている
- `step_2.role` は `TRANSFORM` ではなく `ACTION`
- `step_3.output_type` は `string` ではなく `void`

## Failure Mapping

- Primary: `Intent Drift`
- Secondary: `Under-Spec Capture`
