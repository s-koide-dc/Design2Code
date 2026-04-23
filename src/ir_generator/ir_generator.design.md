# IR Generator Design Document

## 1. Purpose (Updated 2026-04-14)

`IRGenerator` は `StructuredSpec` のステップ列を中間表現（IR）ツリーへ変換する。  
意図推定、カードinality 推定、データフロー連結、必要に応じたシリアライズ/デシリアライズノードの挿入を行い、後続のコード合成工程に決定的な論理骨格を提供する。

## 2. Structured Specification

### Input
- **Description**: `StructuredSpec`（`steps`/`inputs`/`outputs`/`data_sources` を含む）。`steps` のみの簡易リストも受け付ける。
- **Type/Format**: `Dict[str, Any]` または `List[str]`
- **Example**:
  ```json
  {
    "steps": [
      {"id":"step_1","text":"注文一覧を取得する","intent":"FETCH","source_ref":"orders_api","source_kind":"http"}
    ],
    "inputs": [],
    "outputs": []
  }
  ```

### Output
- **Description**: IR ツリーと I/O 情報。
- **Type/Format**: `Dict[str, Any]`
- **Example**:
  ```json
  { "logic_tree": [ { "id":"step_1", "intent":"FETCH" } ] }
  ```

### Core Logic
1. `StructuredSpec` がリスト入力の場合は `steps` を持つ辞書形式へ正規化する。
2. `steps` を順に処理し、`[data_source|...]` 行や入力記述と一致する行はスキップする。
3. `strict_semantics` が有効な場合、各ステップに `ops` または明示的な意図指定がないと例外を投げる。
4. 各ステップに対して `_analyze_step_integrated` を呼び、形態素解析・ベクトル類似度・論理監査（`LogicAuditor`）から intent/role/cardinality/semantic_roles を決定する。
5. 明示された `semantic_roles` / `source_ref` / `source_kind` を上書き・補完し、`semantic_roles.path` や `semantic_roles.name` を必要に応じて付与する。
6. intent を補正する（例: `semantic_roles.url` があれば `HTTP_REQUEST`、`semantic_roles.sql` があれば `PERSIST` へ昇格）。
7. 直前ノードの履歴を参照して `input_link` を決定し、`cardinality` と `output_type` を調整する。
8. `FETCH/HTTP_REQUEST` でコレクション型を返す場合は `JSON_DESERIALIZE` ノードを追加し、`PERSIST` でコレクションを受ける場合はシリアライズ用ノードを挿入する。
9. `CONDITION/LOOP/ELSE/END` を考慮しつつ `logic_tree` を構築して返却する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 1 ステップの `FETCH` を IR ノードへ変換。
  - **Expected Output**: `logic_tree[0].intent == "FETCH"`。
- **Edge Cases**:
  - **Scenario**: `STRICT_SEMANTICS=1` で `ops`/明示意図が無いステップ。
  - **Expected Output / Behavior**: `ValueError` を送出。
  - **Scenario**: `FETCH` の出力型が `List<T>` の場合。
  - **Expected Output / Behavior**: `JSON_DESERIALIZE` ノードが追加される。
  - **Scenario**: `PERSIST` がコレクション入力を受ける場合。
  - **Expected Output / Behavior**: シリアライズ用ノードが挿入される。

## 3. Dependencies
- **Internal**: `morph_analyzer`, `logic_auditor`, `type_system`

## 4. Review Notes
- 2026-04-14: strict_semantics と input_link 決定・intent 補正フローを現行実装に合わせて再確認。
