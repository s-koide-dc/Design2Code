# Case 11: Wrapper Scope Dependency

## Source Scenario

- Scenario: `RetryWrapperMinimal.design.md` 相当の wrapper 文脈観察ケース
- Benchmark role: `WRAPPER` 配下の `first-child` / `second sibling` / `nested child`

## Target Meaning Elements

- wrapper first-child の wrapper 親依存
- wrapper second sibling の逐次 sibling 依存
- wrapper 内 nested loop の first-child が nested loop 親へ依存すること

## Expected Structure Summary

- retry wrapper を開始する
- wrapper 内 first-child でデータを取得する
- 次のノードで取得結果を変換する
- その後 nested loop で各要素を処理する

## Expected IR

```json
{
  "case_id": "case_11_wrapper_scope_dependency",
  "status": "draft",
  "module_name": "WrapperScopeDependency",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "GENERAL",
      "role": "ACTION",
      "target_entity": "Job",
      "cardinality": "SINGLE",
      "output_type": "void",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "WRAP",
          "wrapper_kind": "retry"
        }
      },
      "children": [
        {
          "id": "step_2",
          "type": "ACTION",
          "intent": "FETCH",
          "role": "FETCH",
          "target_entity": "Job",
          "cardinality": "COLLECTION",
          "output_type": "IEnumerable<Job>",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": "step_1",
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "spec_role": "FETCH"
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
          "target_entity": "Job",
          "cardinality": "COLLECTION",
          "output_type": "IEnumerable<Job>",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": "step_2",
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "spec_role": "TRANSFORM",
              "ops": [
                "normalize"
              ]
            }
          },
          "children": [],
          "else_children": []
        },
        {
          "id": "step_4",
          "type": "LOOP",
          "intent": "GENERAL",
          "role": "ITERATE",
          "target_entity": "Job",
          "cardinality": "COLLECTION",
          "output_type": "void",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": "step_3",
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "spec_role": "ITERATE"
            }
          },
          "children": [
            {
              "id": "step_5",
              "type": "ACTION",
              "intent": "DISPLAY",
              "role": "DISPLAY",
              "target_entity": "Job",
              "cardinality": "SINGLE",
              "output_type": "string",
              "source_kind": "memory",
              "source_ref": null,
              "input_link": "step_4",
              "semantic_map": {
                "logic": [],
                "semantic_roles": {
                  "spec_role": "DISPLAY",
                  "property": "Name"
                }
              },
              "children": [],
              "else_children": []
            }
          ],
          "else_children": []
        }
      ],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- wrapper first-child は `input_link = wrapper`
- wrapper second sibling は `input_link = wrapper_first_child`
- nested loop 自体は wrapper 内 sibling として接続される
- nested loop の子 first-child は `input_link = nested_loop`

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_11_wrapper_scope_dependency.observed.json`
```

## Diff Notes

- wrapper first-child は期待どおり `input_link = step_1`
- wrapper second sibling も期待どおり `input_link = step_2`
- nested loop child first-child も期待どおり `input_link = step_4`
- wrapper ノード自体も `spec_role=WRAP` を保持できるようになった
- loop ノードも `intent=GENERAL`, `role=ITERATE`, `spec_role=ITERATE` に改善した
- 一方で wrapper は downstream consumer をまだ持たず、role 保持と消費の間には差が残る

## Failure Mapping

- Primary: `Under-Spec Capture`
- Secondary: `None`
