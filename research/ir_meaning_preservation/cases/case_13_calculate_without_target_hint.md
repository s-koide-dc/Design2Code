# Case 13: Calculate Without Target Hint

## Source Scenario

- Scenario: 最小の自然言語計算指示を単独抽出したケース
- Benchmark role: implicit phrase のみを持つ `CALCULATE`

## Target Meaning Elements

- 明示 target hint なしでの calculation intent 検出
- `CALCULATE` と `GENERAL/ACTION` の境界
- `logic_goals` 不足時の弱化観察

## Expected Structure Summary

- 商品を取得する
- 価格を計算する
- 計算結果を表示する

## Expected IR

```json
{
  "case_id": "case_13_calculate_without_target_hint",
  "status": "draft",
  "module_name": "CalculateWithoutTargetHint",
  "logic_tree": [
    {
      "id": "step_1",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "Product",
      "cardinality": "SINGLE",
      "output_type": "Product",
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
      "type": "ACTION",
      "intent": "CALC",
      "role": "CALC",
      "target_entity": "Product",
      "cardinality": "SINGLE",
      "output_type": "decimal",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1",
      "semantic_map": {
        "logic": [
          {
            "type": "calculation"
          }
        ],
        "semantic_roles": {
          "spec_role": "CALCULATE"
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
      "target_entity": "Product",
      "cardinality": "SINGLE",
      "output_type": "string",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_2",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "DISPLAY",
          "content": "{context}"
        }
      },
      "children": [],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- 研究上の期待形では、計算ノードは `CALCULATE` として保持したい
- ただし現行観測では弱化が起こる可能性が高く、差分自体が研究対象になる
- 表示ノードは計算ノードへ依存する

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_13_calculate_without_target_hint.observed.json`
```

## Diff Notes

- 計算ノードは `intent=GENERAL`, `role=ACTION`, `spec_role=ACTION` に留まった
- `logic_goals` も空で、計算対象を表す補助メタも付かなかった
- Case 12 と比較すると、target hint の有無は metadata 保持には効くが、現状の昇格結果には差を作っていない
- 表示ノードの `input_link = step_2` は保持された

## Failure Mapping

- Primary: `Intent Drift`
- Secondary: `Under-Spec Capture`
