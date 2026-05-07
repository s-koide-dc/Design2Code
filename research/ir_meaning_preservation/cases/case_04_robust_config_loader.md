# Case 04: RobustConfigLoader

## Source Scenario

- Scenario: `scenarios/RobustConfigLoader.design.md`
- Benchmark role: `CONDITION / ELSE / END` を含む最小分岐ケース

## Target Meaning Elements

- 存在確認の条件ノード化
- `then` と `else` の分離
- 条件結果に依存した後続処理の保持

## Expected Structure Summary

- `config.json` の存在を確認する
- 存在する場合は読み込み、内容を表示する
- 存在しない場合は not found メッセージを表示する

## Expected IR

```json
{
  "case_id": "case_04_robust_config_loader",
  "status": "draft",
  "module_name": "RobustConfigLoader",
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
        }
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
        },
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
          "input_link": "step_2",
          "semantic_map": {
            "logic": [],
            "semantic_roles": {
              "spec_role": "DISPLAY"
            }
          },
          "children": [],
          "else_children": []
        }
      ],
      "else_children": [
        {
          "id": "step_5",
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

- `step_1` は `CONDITION` ノード
- `step_2` と `step_3` は `then` 側へ属する
- `step_5` は `else_children` 側へ属する
- `ELSE` と `END` は制御マーカーとして扱う
- 条件ノード自体の `spec_role` は `CHECK` として評価する

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_04_robust_config_loader.observed.json`
```

## Diff Notes

- `CONDITION` と `else_children` は保持された
- `role=CHECK` を期待したが実 IR は `ACTION`
- `step_5.input_link` が条件ノードではなく `step_3` に接続されている
- source 情報は条件ノード側で落ちている

## Failure Mapping

- Primary: `Dependency Loss`
- Secondary: `Intent Drift`
