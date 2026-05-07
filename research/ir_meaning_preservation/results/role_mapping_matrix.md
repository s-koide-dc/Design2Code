# Spec Role to Runtime Role Mapping Matrix

## 1. Purpose

この文書は、優先 5 ケースについて、期待 IR に付与した `spec_role` と、実 IR の既存 `role` を `runtime_role` として読み替えた結果を対応付けるためのものである。

ここでは、観測済み JSON 自体は書き換えない。生データは `observed_ir/` に保持し、研究上の比較はこの文書で行う。

## 2. Reading Rule

- 期待 IR の `semantic_map.semantic_roles.spec_role` を `spec_role` として扱う
- 実 IR の既存 `role` フィールドを、当面 `runtime_role` 相当として扱う
- `role` が `null` の場合は、未割当または比較不能として扱う

## 3. Case-by-Case Mapping

### Case 01: StdinToStdoutTransform

| Step | Expected `spec_role` | Observed `runtime_role` | Status | Note |
|---|---|---|---|---|
| step_1/step_2 | `FETCH` | `FETCH` | Aligned | 取得は後段補正で runtime 上も一致する |
| step_2/step_3 | `TRANSFORM` | `ACTION` | Drift | 変換の仕様意味が一般動作へ圧縮される |
| step_3/step_4 | `DISPLAY` | `DISPLAY` | Aligned | 表示は後段補正で一致する |

### Case 02: ComplexLinqSearch

| Step | Expected `spec_role` | Observed `runtime_role` | Status | Note |
|---|---|---|---|---|
| step_1 | `FETCH` | `FETCH` | Aligned | 読み込みは一致 |
| step_2 | `DESERIALIZE` | `ACTION` | Drift | デシリアライズが独立 role として立たない |
| step_3 | `FILTER` | `ACTION` | Drift | フィルタ意味が一般動作へ圧縮される |
| step_4 | `FILTER` | `ACTION` | Drift | 同上 |
| step_5 | `DISPLAY` | `DISPLAY` | Aligned | 表示は一致 |

### Case 03: BatchProcessProducts

| Step | Expected `spec_role` | Observed `runtime_role` | Status | Note |
|---|---|---|---|---|
| step_1_fetch | `FETCH` | `FETCH` | Partial | 取得は見えるが、実 IR ではデシリアライズと圧縮されている |
| step_1_deserialize | `DESERIALIZE` | `FETCH` | Drift | 期待した二段構造が 1 ノードへ畳み込まれる |
| step_2 | `ITERATE` | `ACTION` | Drift | 反復の仕様役割が runtime role に現れない |
| step_3 | `DISPLAY` | `DISPLAY` | Aligned | ループ本体の表示は一致 |

### Case 04: RobustConfigLoader

| Step | Expected `spec_role` | Observed `runtime_role` | Status | Note |
|---|---|---|---|---|
| step_1 | `CHECK` | `ACTION` | Drift | 条件確認が一般動作へ圧縮される |
| step_2 | `FETCH` | `FETCH` | Aligned | then 側の読み込みは一致 |
| step_3 | `DISPLAY` | `DISPLAY` | Aligned | then 側の表示は一致 |
| step_5 | `DISPLAY` | `DISPLAY` | Aligned | else 側の表示 role 自体は一致 |

### Case 05: SyncExternalData

| Step | Expected `spec_role` | Observed `runtime_role` | Status | Note |
|---|---|---|---|---|
| step_3/step_1 | `FETCH` | `READ` | Drift | HTTP 取得が runtime では I/O 操作としてのみ扱われる |
| step_4/step_2 | `DESERIALIZE` | `ACTION` | Drift | デシリアライズが一般動作へ圧縮される |
| step_5/step_3 | `PERSIST` | `PERSIST` | Aligned | 保存 role 自体は後段補正で一致する |
| step_7/step_4 | `RETURN` | `ACTION` | Drift | return が独立 role として立たない |

## 4. Cross-Case Summary

### Frequently Aligned

- `FETCH`
  - file 系では `FETCH` へ補正されやすい
- `DISPLAY`
  - 後段補正で `DISPLAY` に揃う傾向がある
- `PERSIST`
  - 保存系は後段補正で `PERSIST` に揃う

### Frequently Drifted

- `TRANSFORM`
  - `ACTION` に圧縮されやすい
- `DESERIALIZE`
  - `ACTION` または `FETCH` に吸収されやすい
- `FILTER`
  - `ACTION` に圧縮されやすい
- `CHECK`
  - `ACTION` に圧縮されやすい
- `ITERATE`
  - runtime role には表れにくい
- `RETURN`
  - `ACTION` に留まりやすい

## 5. Interim Interpretation

現在の実装では、`runtime_role` は主に「生成・実行に直接効く操作クラス」を優先しており、以下は比較的保存されやすい。

- 取得
- 表示
- 保存

一方で、以下のような仕様意味 role は保存されにくい。

- 変換
- デシリアライズ
- フィルタ
- 条件確認
- 反復
- return

この偏りは、現行 role 体系が仕様意味を表すには粗すぎることを示している。

## 6. Immediate Next Step

次に進む場合は、以下のどちらかを選ぶのが自然である。

1. `spec_role` を保持するための最小設計変更案をまとめる
2. まず `DESERIALIZE`, `FILTER`, `CHECK` の 3 役割だけに絞って、どこで失われるかをさらに深掘りする
