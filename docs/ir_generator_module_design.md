# IR Generator / Semantic Metadata Module Design

## 1. 対象
この文書は、設計書から IR を生成する更新済みモジュール群と、そこで生成した metadata を downstream がどう消費するかを対象にする。

対象モジュール:
- `src/ir_generator/ir_generator.py`
- `src/ir_generator/check_resolution.py`
- `src/ir_generator/promotion_rules.py`
- `src/ir_generator/target_resolution.py`
- `src/ir_generator/spec_role_rules.py`
- `src/code_synthesis/action_synthesizer.py`
- `src/code_synthesis/semantic_binder.py`
- `src/code_synthesis/action_handlers/calc_ops.py`

## 2. 設計上の問題設定
従来の問題は、IR が runtime 都合の `intent` / `role` に寄りすぎ、以下が十分保持されないことだった。

- `CHECK`, `FILTER`, `CALCULATE` の仕様意味
- 条件・計算・述語がどう解決されたかという provenance
- schema alias と property canonicalization の境界
- structure parent と sibling の依存境界

更新後の設計は、これらを runtime から独立した metadata として保持し、下流で保守的に使う。

## 3. 上流から下流への責務分担

### 3.1 `IRGenerator`
責務:
- clause 分解
- 構造ノード化
- coarse intent / role 推定
- `spec_role` と role-specific metadata の付与
- structural dependency の確定
- auto bridge node の挿入

保持すべきもの:
- runtime `intent` / `role`
- `semantic_map.spec_role`
- provenance / resolution metadata
- `input_link` と構造境界

### 3.2 downstream
責務:
- 保存済み metadata を読んで execution choice を補正する
- provenance が弱い場合は concretization を弱める
- metadata が十分でない場合は generic path か TODO 停止に寄せる

## 4. `ir_generator.py` の orchestration phases

### Phase 1: Raw step normalization
- 生 step の文字列化
- data source 行や入力説明行の除外
- clause 抽出

### Phase 2: Step-local semantic analysis
- `intent`, `role`, `cardinality`, `target_entity` の粗い分析
- `logic_auditor` 結果の取得
- explicit semantic roles の統合

### Phase 3: Role-specific semantic resolution
- `spec_role` 推定
- `CHECK` metadata 付与
- `FILTER` / `CALCULATE` 昇格
- `entity_resolution`, `subject_resolution`, `predicate_resolution`, `collection_resolution` の補強

### Phase 4: Final runtime coercion
- runtime `intent` / `role` の最終決定
- `source_kind` の最終補完
- `input_link` の決定

### Phase 5: Node emission
- IR node 構築
- structure attach
- context history 更新

### Phase 6: Auto node insertion
- `JSON_DESERIALIZE`
- `JSON_SERIALIZE`

## 5. helper module ごとの責務

### 5.1 `check_resolution.py`
入出力:
- 入力: token 列, logic goals, source info, target entity
- 出力: `check_kind`, `check_subject`, `check_operator`, `check_value`, `expected_truth`, `subject_resolution`

ルール:
- `null` は `null_check`
- `存在` / quoted literal は `exists_check`
- 比較 logic goal は `comparison_check`

### 5.2 `promotion_rules.py`
入出力:
- 入力: lexical signal, logic goals, upstream collection context, semantic roles
- 出力: `FILTER` / `CALCULATE` への昇格可否

ルール:
- `FILTER`: 曖昧語彙 + predicate logic + collection context
- `CALCULATE`: target metadata + 計算意図 signal

### 5.3 `target_resolution.py`
入出力:
- 入力: `entity_schema`, property token, current entity, history
- 出力: canonical property, owner entities, `entity_resolution`, property provenance

ルール:
- canonicalization は schema alias 明示時のみ
- unique owner -> `unique_owner`
- current entity が強い -> `explicit_entity`
- owner 複数 -> `ambiguous`
- history だけで解決 -> `history_fallback`

### 5.4 `spec_role_rules.py`
入出力:
- 入力: runtime intent, node type, logic goals
- 出力: `spec_role`

目的:
- runtime role に落とし込む前の仕様意味を固定する

## 6. structural dependency 設計

### 6.1 branch / block rules
- block の first child は structural parent に接続
- block の second sibling 以降は直前 sibling に接続
- `ELSE` は `CONDITION` を branch base にする

### 6.2 期待効果
- then / else 間の誤接続防止
- loop body 内 sibling の collection 優先誤接続防止
- wrapper / loop / condition を同一原理で扱える

## 7. metadata の下流消費

### 7.1 `ActionSynthesizer`
- `spec_role=DESERIALIZE` を `JSON_DESERIALIZE` に橋渡し
- `spec_role=FILTER` を `LINQ` に橋渡し
- `spec_role=CALCULATE` を `CALC` 処理へ橋渡し

### 7.2 `SemanticBinder`
- `CHECK` metadata を優先して条件式生成
- weak provenance では schema/property 逆引きを抑止
- exact scope がある history provenance だけ限定的に許可

### 7.3 `calc_ops`
- `entity_resolution` に応じて concretization を変える
- `unique_owner` / `explicit_entity`: 通常合成
- `history_fallback`: exact target 限定
- `ambiguous`: cross-entity fallback 禁止、必要なら TODO 停止

## 8. schema alias policy との接続
この設計は alias admission policy と一体で動く。

- alias の供給元: `entity_schema.properties[].aliases`
- canonicalization 条件: exact match only
- admission timing は runtime 推論ではなく schema policy で管理

つまり、`IRGenerator` は alias を勝手に発明せず、schema に供給されたものだけを deterministic に使う。

## 9. 保守上の指針
- 新しい semantic rule を足すときは、まず `spec_role` / provenance / alias policy のどこに属するかを決める。
- `ir_generator.py` に直接 if を増やす前に、既存 domain helper に属するかを確認する。
- 弱い provenance のときは精度を上げるより過剰具体化を止める方を優先する。
- schema alias 追加は runtime の都合ではなく benchmark need と admission policy で決める。

## 10. 現在の着地点
このモジュール設計の着地点は、IR を「単なる中間フォーマット」ではなく、仕様意味・解決由来・保守的合成方針を保持する安定層として扱うことにある。
