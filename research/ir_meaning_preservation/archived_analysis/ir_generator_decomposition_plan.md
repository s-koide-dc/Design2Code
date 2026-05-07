# IRGenerator Decomposition Plan

## 1. Purpose

この文書は、`IRGenerator` の肥大化を場当たり的なクラス分割で処理するのではなく、研究で確立した意味概念に沿って整理するための分割方針を定義するものである。

目的は 2 つある。

1. `IR meaning preservation` の観測点を壊さずに保守性を上げる
2. 役割ごとの規則追加が `IRGenerator` 全体の if 分岐へ埋没するのを防ぐ

## 2. Current Position

現時点で `IRGenerator` に集中しているものは、大きく次の 4 系統である。

1. structure / chaining
2. intent / role promotion
3. role-specific semantic resolution
4. target/source/entity inference

研究上はすでにこれらが別論点として分かれているため、実装上もこの単位で整理するのが自然である。

## 3. Why Not Immediate Physical Split

いま直ちに複数クラスや複数モジュールへ物理分割すると、研究途中の境界が再び揺れる危険がある。

特に避けたいのは次の失敗である。

- `CHECK`, `FILTER`, `CALCULATE` のような role ごとの仮説が固まる前に抽象レイヤを先に作ってしまう
- utility 化した結果、どの規則がどの研究論点に属するのか見えにくくなる
- 下流依存まで同時に触って観測と修正が混ざる

したがって、最初にやるべきなのは「論点ごとの内部境界を固定すること」であって、「ファイル数を増やすこと」ではない。

## 4. Proposed Internal Domains

`IRGenerator` の責務は、少なくとも次の 5 domain に分けて考える。

### 4.1 Structural Dependency Domain

担当:

- block / branch / loop の依存規則
- `input_link`
- `children`, `else_children`
- structural parent / sibling dependency

現在の代表関数・論点:

- `generate()` 後半の chaining 判定
- `structural_dependency_rule.md`
- `dependency_loss_trace.md`

### 4.2 Target Resolution Domain

担当:

- `target_entity`
- source / entity / no-history base inference
- history fallback

現在の代表関数・論点:

- `_identify_target_entity(...)`
- `_infer_calculate_target_entity(...)`
- `entity_resolution`

### 4.3 CHECK Resolution Domain

担当:

- `check_kind`
- `check_subject`
- `subject_resolution`
- `source_ref/source_kind` for condition

現在の代表関数・論点:

- `_infer_check_metadata(...)`
- `_infer_check_target_entity(...)`
- `_infer_null_check_subject_metadata(...)`

### 4.4 Promotion Domain

担当:

- `CALCULATE` 昇格
- `FILTER` 昇格
- 将来の `TRANSFORM` / `AGGREGATE` 分岐

現在の代表関数・論点:

- `_should_promote_to_calculate(...)`
- `_should_promote_to_filter(...)`
- `calculate_promotion_rule.md`
- `filter_promotion_rule.md`

### 4.5 Spec Role Domain

担当:

- `spec_role`
- role-specific metadata bridge
- runtime role との分離

現在の代表関数・論点:

- `_infer_spec_role(...)`
- `role_layer_definition.md`
- `structural_role_bridge.md`

## 5. Recommended Refactoring Shape

最初の整理は、外部 API を変えずに `IRGenerator` 内部 helper 群を domain ごとに寄せる形にする。

つまり次の順で進める。

1. domain 単位で関数群を並べ替える
2. domain ごとに小さな private helper を増やす
3. comment header で責務境界を明示する
4. その後にだけ、必要なら `src/ir_generator/` 配下の module へ切り出す

## 6. Phase Plan

### Phase A: In-File Decomposition

目的:

- 物理分割前に責務境界を固定する

作業:

- helper を domain ごとに再配置
- comment header を追加
- `generate()` の中で domain ごとの処理位置を見える化

進捗:

- domain header / phase comment 追加: 実施済み
- structural dependency helper 局所化: 実施済み
  - `last collection` 探索
  - structural `input_link` 決定
  - `ELSE` branch activation
  - structural node attachment / block push
- final coercion / pre-emission helper 局所化: 実施済み
  - final intent / runtime-role coercion
  - source-kind resolution
  - cardinality finalization
  - node construction
- auto-node insertion helper 局所化: 実施済み
  - JSON deserialize insertion
  - JSON serialize insertion
  - upstream string-output guard
  - current-structure append helper
- role-specific semantic resolution helper 束ね: 実施済み
  - structure-role annotation
  - CHECK metadata enrichment
  - CALCULATE entity-resolution bridge
- orchestration control helper 局所化: 実施済み
  - `ELSE` / `END` handling
  - redundant `DATABASE_QUERY` suppression
  - context-history append

### Phase B: Domain Helper Extraction

目的:

- 特に長い role-specific helper 群を局所化する

候補:

- `check_resolution`
- `promotion_rules`
- `target_resolution`
- `spec_role_rules`

この段階ではまだクラス分割ではなく、module-level helper でもよい。

進捗:

- `check_resolution.py`: 実施済み
- `promotion_rules.py`: 実施済み
- `target_resolution.py`: 実施済み
- `spec_role_rules.py`: 実施済み

### Phase C: Service-Level Extraction

目的:

- 安定した domain を `IRGenerator` から切り出す

候補:

- `CheckResolutionEngine`
- `PromotionRules`
- `TargetResolutionEngine`

この段階は研究論点が十分安定してからでよい。

## 7. What Must Stay Central For Now

現段階では、次の 2 つはまだ `IRGenerator` 中央に残すべきである。

1. `generate()` の構造制御フロー
2. `analysis -> semantic_map -> final_intent -> node emit` の主経路

ここを早く分割すると、meaning preservation の主因果が見えにくくなる。

## 8. Immediate Refactoring Targets

今の状態で最初に整理価値が高いのは次の 3 つである。

1. `CHECK Resolution Domain`
   - すでに `check_kind`, `subject_resolution` まで揃っている
   - domain として比較的閉じている
2. `Promotion Domain`
   - `CALCULATE` と `FILTER` の昇格規則が別々に増え始めている
   - 今のうちに同じ並びへ寄せる価値が高い
3. `Target Resolution Domain`
   - no-history base, history fallback, schema owner 解決がまとまってきた

逆に `Structural Dependency Domain` はまだ `generate()` 主経路との結びつきが強いので、先に概念整理だけに留める方がよい。

## 9. Success Criteria

整理が成功したとみなす条件は次の通りである。

1. `IRGenerator` の規則追加がどの domain に属するかすぐ説明できる
2. `CHECK`, `FILTER`, `CALCULATE` の変更が互いの文脈を汚しにくくなる
3. 既存 benchmark と研究文書の対応関係が読みやすくなる
4. 物理分割をまだしていなくても、内部構造の意図が明確になる

## 10. Immediate Next Step

次にやるべきことは、実際の大分割ではなく、`IRGenerator` 内に domain header を入れて helper 群を並べ替える最初の in-file decomposition である。
