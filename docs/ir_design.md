# IR (Intermediate Representation) 設計

## 1. 目的
自然言語の設計書から直接 C# を生成するのではなく、まず意味を保持した IR に落とすことで、以下を成立させる。

- 構造保持: `CONDITION` / `LOOP` / `WRAPPER` の入れ子と依存境界をコード生成前に固定する。
- 意味保持: runtime 都合の `intent` / `role` とは別に、仕様意味を `spec_role` と補助 metadata で保持する。
- 保守的合成: provenance が弱い場合は downstream で過剰具体化せず、generic path または明示停止へ寄せる。
- 決定論的生成: schema / 明示 metadata / 固定ロジックに基づく一回限りの解釈で生成を安定化する。

## 2. IR の基本モデル
IR は `logic_tree` を持つ JSON 抽象木であり、ノードは「構造」と「意味 metadata」の両方を持つ。

### 2.1 構造ノード
- `ACTION`: 最小実行単位。
- `CONDITION`: 条件分岐。`children` と `else_children` を持つ。
- `LOOP`: 反復構造。`children` を持つ。
- `WRAPPER`: retry などの構造的包摂。`children` を持つ。
- `ELSE` / `END`: 生成時の制御マーカー。最終 IR の構造境界形成にだけ使う。

### 2.2 実行意味
- `intent`: runtime の実行意図。例: `FETCH`, `DISPLAY`, `PERSIST`, `LINQ`, `CALC`, `JSON_DESERIALIZE`。
- `role`: runtime 側の粗い役割。下流合成で使う。
- `spec_role`: 仕様意味の役割。`runtime_role` に潰さず保持する。

### 2.3 主要 `spec_role`
- `FETCH`
- `DESERIALIZE`
- `FILTER`
- `TRANSFORM`
- `CHECK`
- `CALCULATE`
- `DISPLAY`
- `PERSIST`
- `RETURN`
- `ITERATE`
- `WRAP`

## 3. ノード共通フィールド
- `id`: `step_1` 形式のノード ID。
- `type`: `ACTION`, `CONDITION`, `LOOP`, `WRAPPER` などの構造型。
- `intent`: runtime intent。
- `role`: runtime role。
- `target_entity`: 対象エンティティ。
- `cardinality`: `SINGLE` / `COLLECTION`。
- `output_type`: 推定出力型。
- `source_kind`: `file`, `db`, `http`, `env`, `stdin`, `memory` など。
- `source_ref`: ファイル名や接続先名などの参照。
- `input_link`: 上流依存ノード ID。
- `children`: 構造ノードの true/body 側。
- `else_children`: `CONDITION` の false 側。
- `semantic_map`: 意味保持用 metadata。

## 4. `semantic_map` の設計
`semantic_map` は runtime 判定を補助するだけではなく、意味保存と下流保守化の中核になる。

### 4.1 中核フィールド
- `spec_role`: 仕様意味。
- `logic`: `LogicAuditor` による比較・計算・述語の抽出結果。
- `semantic_roles`: 明示タグまたは補完された役割 metadata。

### 4.2 CHECK metadata
- `check_kind`: `exists_check`, `null_check`, `comparison_check`。
- `check_subject`
- `check_operator`
- `check_value`
- `expected_truth`
- `subject_resolution`

### 4.3 CALCULATE metadata
- `property`
- `target_hint`
- `entity_resolution`

### 4.4 FILTER metadata
- `property`
- `predicate_resolution`
- `collection_resolution`

## 5. Provenance / Resolution の考え方
意味保存では「解決できた値」だけでなく「どう解決したか」を保持する。

### 5.1 代表的な resolution
- `quoted_literal`
- `explicit_subject`
- `schema_property`
- `history_subject`
- `logic_goal`
- `explicit_input_link`
- `history_predicate`
- `unique_owner`
- `explicit_entity`
- `history_fallback`
- `ambiguous`

### 5.2 設計原則
- 明示情報が最優先。
- schema-backed な canonicalization は schema 側の宣言がある場合に限定する。
- history ベースの解決は exact scope に閉じる。
- 曖昧性は消さず metadata として残す。

## 6. Alias と canonical property
property surface から canonical property への写像は runtime heuristic ではなく schema policy で管理する。

### 6.1 schema alias
`entity_schema.properties[].aliases` に明示された alias のみを canonicalization に使う。

### 6.2 制約
- exact match のみ
- 1 alias -> 1 canonical property
- canonical ambiguity は不許可
- owner ambiguity は保持してよい

### 6.3 IR 上の効果
- `CHECK.subject_resolution = schema_property`
- `FILTER.predicate_resolution = schema_property`
- `property = Stock` のように canonical property を保持

## 7. 構造依存規則
`input_link` は単純な直前ノードチェーンではなく、構造親依存と sibling 依存を分けて決める。

### 7.1 基本規則
- 構造ブロック内の最初の実ノードは structural parent に依存する。
- 同一ブロック内の 2 個目以降は直前 sibling に依存する。
- `ELSE` 側の最初のノードは then 側の末尾ではなく対応 `CONDITION` を branch base にする。

### 7.2 効果
- `CONDITION`, `LOOP`, `WRAPPER` の依存境界を同じ原理で扱える。
- `Dependency Loss` の `Edge Misbinding` と `Boundary Drift` を抑制できる。

## 8. 自動 bridge ノード
IR 生成では意味保存と下流適合のために補助ノードを自動挿入する。

- `FETCH` / string output -> `JSON_DESERIALIZE`
- `PERSIST` / collection input -> `JSON_SERIALIZE`

これらは ad hoc な後処理ではなく、IR 上の明示ノードとして保持する。

## 9. モジュール分解
`IRGenerator` は orchestration を維持しつつ、意味領域ごとに helper module へ分割する。

### 9.1 `src/ir_generator/ir_generator.py`
- 生成フローの orchestration
- 構造制御
- node emission
- auto-node insertion

### 9.2 `src/ir_generator/check_resolution.py`
- `CHECK` の kind / subject / operator / expected truth 推定

### 9.3 `src/ir_generator/promotion_rules.py`
- `FILTER` / `CALCULATE` 昇格条件

### 9.4 `src/ir_generator/target_resolution.py`
- canonical property 解決
- owner entity 解決
- `entity_resolution`

### 9.5 `src/ir_generator/spec_role_rules.py`
- `intent` / `logic` / `node_type` からの `spec_role` 推定

## 10. 下流への橋渡し
IR は保存して終わりではなく、`src/code_synthesis` で消費される。

### 10.1 `ActionSynthesizer`
- `spec_role` から execution intent を補正する。
- `FILTER` -> `LINQ`
- `DESERIALIZE` -> `JSON_DESERIALIZE`

### 10.2 `SemanticBinder`
- `CHECK` metadata を優先して条件式を生成する。
- provenance が弱い場合は schema 逆引きを抑止する。

### 10.3 `calc_ops`
- `entity_resolution` に応じて保守度を変える。
- `ambiguous` は cross-entity fallback を止め、必要なら TODO 停止する。

## 11. 設計上の主張
この IR 設計の要点は次の 3 点にある。

1. 意味損失の中心は structure collapse ではなく role weakening と provenance under-capture である。
2. 意味保存には runtime intent だけでなく `spec_role` と resolution metadata が必要である。
3. alias 問題は runtime heuristic ではなく schema/policy の admission 問題として扱うべきである。
