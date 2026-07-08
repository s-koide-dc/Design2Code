# MethodStore 設計ドキュメント

## 1. 目的 (Purpose)
`MethodStore` は収集されたメソッド部品を管理し、構造メタデータによる候補絞り込みと、その候補内でのベクトル検索を提供します。

## 2. 構造化仕様 (Structured Specification)

### 2.1. 検索ロジック (search)
1.  **構造フィルタ**: `intent`, `role`, `required_capabilities`, `input_type`, `return_type` を明示メタデータへ照合する。
2.  **要求と候補の分離**: メタデータを持たない候補へ検索要求のintent/capabilityを後付けしない。
3.  **意味距離の利用境界**: ベクトル検索は構造条件を満たす候補内の順序付けにだけ使用する。名称類似度との合成スコアは使わない。
4.  **モデルなし経路**: 構造条件を満たす候補をclass・name・IDの安定順で返し、scoreは`None`とする。

### 2.2. Harvest 正規化 / 品質ゲート
1.  **共通 Policy**: `MethodStorePolicy` が source analysis、reflection、NuGet、seed script 由来の entry を同じ規則で正規化する。
2.  **Metadata 補完**: `role` / `capabilities` / `params[].role` / `origin` / `summary` / `usings` / `has_side_effects` を保存前に補完する。
3.  **構造化 Policy File**: 低価値 API の除外ルール、許可 capability、semantic role は `resources/method_store_policy.json` で管理する。
4.  **低価値 API の除外**: delegate 呼び出し、object protocol、lifecycle、HTTP header parser、metadata service など、合成候補として使いにくい harvested API は保存入口で破棄する。
5.  **Pruning Audit**: `MethodStorePolicy.get_audit_summary()` は accepted / pruned / prune_reasons を返し、harvest 経路はこの結果を戻り値または `last_policy_audit` で追跡できる。
6.  **Map 優先**: `resources/method_capability_map.json` に明示された intent / capabilities / param roles は推論より優先する。

### 2.3. Vector DB 再構築
1.  **Source of Truth**: `resources/method_store.json` を master とし、`resources/vectors/vector_db/method_store_meta.json` と `method_store_vectors.npy` は派生物として扱う。
2.  **Forced Rebuild**: `rebuild_index_from_source` は既存 vector DB の内容や更新時刻に依存せず、master JSON を読み直して正規化済み entry から index を作り直す。
3.  **Save Consistency**: 保存時に collection と `items` の件数が一致しない場合は、ゼロ埋めではなく現在の `items` から vector を再生成する。

### 2.4. 学習機能
- **セマンティック・フィードバック**: `record_semantic_feedback` により、意図ごとの成功・失敗履歴を記録し、動的にスコアを調整。

### 2.5. 入力 / 出力
- **Input**: `query`, `limit` と任意の構造条件。
- **Output**: 構造条件を満たすメソッド候補リスト。

## 3. 依存関係
- `scoring_rules.json`: 基本配点ルール。
- `current_project_context.json`: パッケージ利用状況。
- `LightVectorDB`: 高速な近傍探索。

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.
- 2026-04-21: `method_store_meta.json` / `method_store_vectors.npy` は `config.storage_dir`（`resources/vectors/vector_db`）へ統一し、旧配置（workspace root / `resources` / `cache`）は起動時移行で整理する構成に更新。
- 2026-06-25: `MethodStorePolicy` を追加し、複数 harvest 経路から入る method entry を共通の正規化・pruning・capability map 適用で品質ゲートする構成へ更新。
- 2026-06-25: vector DB の rebuild は `method_store.json` を唯一の入力として強制再生成し、保存時の不整合は再ベクトル化で修復する構成へ更新。
- 2026-07-01: intent/capabilityの事前フィルタを必須化し、要求メタデータの候補への後付けと名称類似度合成を削除。
- 2026-06-25: pruning ルールを `resources/method_store_policy.json` に移し、pruning 理由の audit を harvest 経路から追跡できる構成へ更新。

