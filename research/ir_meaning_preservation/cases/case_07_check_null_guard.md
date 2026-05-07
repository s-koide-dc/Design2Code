# Case 07: Check Null Guard

## Source Scenario

- Scenario: `scenarios/SampleProject.design.md` と `scenarios/OrdersProject.design.md` の null-return パターンを抽象化
- Benchmark role: `null_check` の最小ケース

## Target Meaning Elements

- fetch 結果に対する null guard
- `CHECK` と `RETURN` の境界
- `expected_truth=false` の保持

## Expected Structure Summary

- 対象ユーザーを取得する
- 取得結果が null でないかを確認する
- null なら null を返す
- null でなければユーザー名を表示する

## Expected IR

```json
{
  "case_id": "case_07_check_null_guard",
  "status": "draft",
  "module_name": "CheckNullGuard",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "User",
      "cardinality": "SINGLE",
      "output_type": "User",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": null,
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
      "id": "step_2",
      "type": "CONDITION",
      "intent": "EXISTS",
      "role": "CHECK",
      "target_entity": "User",
      "cardinality": "SINGLE",
      "output_type": "bool",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1",
      "condition_expression": "user != null",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "CHECK"
        },
        "check_kind": "null_check",
        "check_subject": "user",
        "expected_truth": false
      },
      "children": [
        {
          "id": "step_4",
          "type": "ACTION",
          "intent": "DISPLAY",
          "role": "DISPLAY",
          "target_entity": "User",
          "cardinality": "SINGLE",
          "output_type": "string",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": "step_1",
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
      "else_children": [
        {
          "id": "step_3",
          "type": "ACTION",
          "intent": "RETURN",
          "role": "RETURN",
          "target_entity": "User",
          "cardinality": "SINGLE",
          "output_type": "User?",
          "source_kind": "memory",
          "source_ref": null,
          "input_link": null,
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "spec_role": "RETURN",
              "return_value": "null"
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

- `step_2` は「null でないか」の guard だが、IR では `null_check` として保持する
- `expected_truth=false` は null 側分岐の存在を示す
- `DISPLAY` は `step_1` の取得結果を使う
- `RETURN` は判定失敗時の early exit

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_07_check_null_guard.observed.json`
```

## Diff Notes

- `check_kind=null_check` と `expected_truth=false` は保持された
- `check_subject=user` は期待どおり保持された
- 条件ノードの `intent/role` は `EXISTS/CHECK` まで改善した
- `target_entity=User` まで改善した
- `RETURN` 分岐はまだ観測ケースに入れておらず、false 分岐の early exit は未評価
- 生成条件式は `user == null` で、条件種別と対象同定の両方が保持された

## Failure Mapping

- Primary: `Under-Spec Capture`
- Secondary: `None`
