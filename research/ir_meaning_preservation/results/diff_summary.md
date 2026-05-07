# Initial Diff Summary

## Scope

この文書は、優先 5 ケースについて、期待 IR と初回採取した実 IR の差分を粗く整理したものである。

## Common Tendencies

- `role` が期待より弱い。`TRANSFORM`, `FILTER`, `CHECK` を期待しても、実 IR は `ACTION` や `READ` に寄る傾向がある。
- `source_ref` と `source_kind` の保持が不安定。明示的な data source 宣言がないケースでは `source_ref` が落ちやすい。
- `output_type` は `DISPLAY` で `void` に寄る。期待 IR で表示対象の流れを追うために `string` と見なした箇所は実 IR とずれる。
- `semantic_map.logic` に実装由来の比較情報が入る。研究上の期待 IR では補助情報として扱うか、比較対象から外すかを次段で決める必要がある。

## Case Notes

### Case 01: StdinToStdoutTransform

- 構造は概ね一致。
- ずれは `id` の開始番号、`role=TRANSFORM` ではなく `ACTION`、`DISPLAY.output_type=void`。
- `stdin` source 自体は保持されている。

### Case 02: ComplexLinqSearch

- 依存連鎖は概ね一致。
- `source_ref=users.json` が落ちている。
- `LINQ.role` が `FILTER` ではなく `ACTION`。
- `DISPLAY.cardinality` と `output_type` が期待と異なる。

### Case 03: BatchProcessProducts

- `LOOP` 構造は保持された。
- 前段の `FETCH + JSON_DESERIALIZE` が 1 ノードに圧縮されている。
- `Product` ではなく `Item` に寄っている箇所があり、entity 推定が弱い。

### Case 04: RobustConfigLoader

- `CONDITION` と `else_children` は保持された。
- `step_5.input_link` が `step_1` ではなく `step_3` に接続されており、依存解釈が不自然。
- 条件ノードの `role` と source 情報が弱い。

### Case 05: SyncExternalData

- `HTTP_REQUEST -> JSON_DESERIALIZE -> PERSIST -> RETURN` の直列構造は保持された。
- `HTTP_REQUEST.role` が `FETCH` ではなく `READ`。
- `PERSIST.cardinality` が `COLLECTION` 期待に対して `SINGLE`。
- `RETURN` の補助意味情報が薄い。
