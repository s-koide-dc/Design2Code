# Case 05: SyncExternalData

## Source Scenario

- Scenario: `scenarios/SyncExternalData.design.md`
- Benchmark role: `http` と `db` を跨ぐ複合同期ケース

## Target Meaning Elements

- source_kind=`http` と source_kind=`db` の区別
- `HTTP_REQUEST -> JSON_DESERIALIZE -> PERSIST` の連鎖
- 保存先 source_ref とデータ依存の保持

## Expected Structure Summary

- HTTP API から商品 JSON を取得する
- JSON を商品集合へ変換する
- 商品集合をローカル DB に保存する
- 成功として `true` を返す

## Expected IR

```json
{
  "case_id": "case_05_sync_external_data",
  "status": "draft",
  "module_name": "SyncExternalData",
  "logic_tree": [
    {
      "id": "step_3",
      "type": "ACTION",
      "intent": "HTTP_REQUEST",
      "role": "FETCH",
      "target_entity": "string",
      "cardinality": "SINGLE",
      "output_type": "string",
      "source_kind": "http",
      "source_ref": "product_api",
      "input_link": null,
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "FETCH",
          "url": "https://api.example.com/products"
        }
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_4",
      "type": "ACTION",
      "intent": "JSON_DESERIALIZE",
      "role": "TRANSFORM",
      "target_entity": "Product",
      "cardinality": "COLLECTION",
      "output_type": "IEnumerable<Product>",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": "step_3",
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
      "id": "step_5",
      "type": "ACTION",
      "intent": "PERSIST",
      "role": "PERSIST",
      "target_entity": "Product",
      "cardinality": "COLLECTION",
      "output_type": "void",
      "source_kind": "db",
      "source_ref": "local_db",
      "input_link": "step_4",
      "semantic_map": {
        "logic": [],
        "semantic_roles": {
          "spec_role": "PERSIST",
          "sql": "INSERT INTO Products (Name, Price) VALUES (@Name, @Price)"
        }
      },
      "children": [],
      "else_children": []
    },
    {
      "id": "step_7",
      "type": "ACTION",
      "intent": "RETURN",
      "role": "ACTION",
      "target_entity": "bool",
      "cardinality": "SINGLE",
      "output_type": "bool",
      "source_kind": "memory",
      "source_ref": null,
      "input_link": null,
      "semantic_map": {
        "logic": [
          {
            "type": "literal_return",
            "value": "true"
          }
        ],
        "semantic_roles": {
          "spec_role": "RETURN",
          "return_value": "true",
          "return_value_resolution": "literal_boolean"
        }
      },
      "children": [],
      "else_children": []
    }
  ]
}
```

## Expected Node Notes

- `step_3` は `http` source を持つ取得ノード
- `step_4` は `step_3` 依存の変換ノード
- `step_5` は `db` source を持つ保存ノード
- `step_7` は最終 `RETURN` ノード
- `HTTP_REQUEST` の期待 `spec_role` は `FETCH` とし、実装上の `READ` と区別して評価する

## Observed IR

```json
See `research/ir_meaning_preservation/results/observed_ir/case_05_sync_external_data.observed.json`
```

## Diff Notes

- 大きな直列構造は保持された
- `HTTP_REQUEST.role` が `FETCH` ではなく `READ`
- `PERSIST.cardinality` が `COLLECTION` 期待に対して `SINGLE`
- `RETURN` の runtime role はなお粗いが、literal return metadata 自体は保持できるようになった

## Failure Mapping

- Primary: `Intent Drift`
- Secondary: `Under-Spec Capture`
