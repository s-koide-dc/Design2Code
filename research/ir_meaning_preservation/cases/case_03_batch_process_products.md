# Case 03: BatchProcessProducts

## Source Scenario

- Scenario: `scenarios/BatchProcessProducts.design.md`
- Benchmark role: 最小の `LOOP` 構造確認

## Target Meaning Elements

- file 読み込みからリスト化までの前段処理
- `LOOP` と `END` の構造保持
- ループ本体の `DISPLAY` 子ノード化

## Expected Structure Summary

- 商品一覧を読み込み、リスト化する
- 商品ごとに繰り返す
- ループ内で `Name` を表示する

## Expected IR

```json
{
  "case_id": "case_03_batch_process_products",
  "status": "draft",
  "module_name": "BatchProcessProducts",
  "logic_tree": [
    {
      "id": "step_1_fetch",
      "type": "ACTION",
      "intent": "FETCH",
      "role": "FETCH",
      "target_entity": "Product",
      "cardinality": "SINGLE",
      "output_type": "string",
      "source_kind": "file",
      "source_ref": "products.json",
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "FETCH",
          "path": "products.json"
        }
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_1_deserialize",
      "type": "ACTION",
      "intent": "JSON_DESERIALIZE",
      "role": "TRANSFORM",
      "target_entity": "Product",
      "cardinality": "COLLECTION",
      "output_type": "List<Product>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1_fetch",
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
      "id": "step_2",
      "type": "LOOP",
      "intent": "GENERAL",
      "role": "ACTION",
      "target_entity": "Product",
      "cardinality": "COLLECTION",
      "output_type": "void",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_1_deserialize",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "ITERATE"
        }
      },
      "children": [
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
              "property": "Name"
            }
          },
          "children": [],
          "else_children": []
        }
      ],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- 読み込みと JSON 変換は前段の直列ノードとして必要になる可能性がある
- `LOOP` は構造ノードであり、平坦な `DISPLAY` 列にしない
- ループ本体ノードは `children` 側へ入る
- `step_2` の `spec_role` は構造的な `ITERATE` として扱う

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_03_batch_process_products.observed.json`
```

## Diff Notes

- `LOOP` 構造は保持された
- 前段の読み込みと JSON 変換が 1 ノードに圧縮されている
- `target_entity` が `Product` ではなく `Item` に寄っている
- `source_kind/source_ref` が保持されていない

## Failure Mapping

- Primary: `Under-Spec Capture`
- Secondary: `Source Drift`
