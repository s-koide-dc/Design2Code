# RepairKnowledgeBase Design Document

## 1. Purpose (Updated 2026-02-10 10:45)
`RepairKnowledgeBase` は、テスト修復のための知識ベースです。過去の「失敗原因（エラーメッセージ）」と「解決策（修正方針）」のペアを、自然言語の意味（ベクトル）に基づいて蓄積・検索します。これにより、AIエージェントは未知のエラーに対しても、過去の類似事例から最適な修復アクションを選択できるようになります。

`SemanticSearchBase` を継承し、ハイブリッド検索（セマンティック検索 + キーワード検索）をサポートします。

## 2. Structured Specification

### 2.1. 知識の構造
データは `resources/repair_knowledge.json` に永続化され、意味ベクトルは `resources/vectors/vector_db/repair_knowledge_vectors.npy` に保存されます。
`repair_knowledge_meta.json` / `repair_knowledge_vectors.npy` は `ConfigManager.storage_dir`（`resources/vectors/vector_db`）へ統一し、旧配置（workspace root / `resources` / `cache`）のファイルは初期化時に移行されます。

- **Patterns**:
    - `error_message_regex`: エラーメッセージの特徴的なパターン。
    - `root_cause`: 推定される根本原因（`logic_error`, `null_reference` 等）。
    - `fix_direction`: 成功した修正アクション（`self_healing_test`, `add_null_validation` 等）。
- **Negative Feedbacks**: 過去のビルド失敗等の「負の体験」を記録。
- **Fix Stats**: 各原因に対する修正方針の成功率統計。

### 2.2. インターフェース定義

#### Input (経験の蓄積)
- `error_type` (str): 発生したエラーの種類（例外クラス名やエラーメッセージ）。
- `root_cause` (str): 推定された根本原因（`logic_error`, `null_reference` 等）。
- `fix_type` (str): 適用した修正アクション（`self_healing_test`, `add_null_validation` 等）。
- `success` (bool): その修正でテストがパスしたかどうか。

#### Output (修正方針の取得)
- `fix_direction` (str | None): 最も類似した過去の成功事例に基づく修正方針。

### 2.3. Core Logic

#### 1. 方針取得 (`get_best_fix_direction`)
1. **ハイブリッド検索**:
   - `SemanticSearchBase` を用い、入力された `error_message` と既存パターンのセマンティック類似度を計算。
   - 同時に、正規表現による文字列一致（キーワード一致）を評価。
2. **スコアリング**:
   - セマンティック重み 0.7、キーワード重み 0.3 で統合スコアを算出。
3. **しきい値判定**:
   - スコアが `semantic_threshold`（デフォルト: 0.85）以上の最高評価パターンを選択し、その `fix_direction` を返却。

#### 2. 成功体験の学習 (`add_repair_experience`)
1. **統計更新**: `root_cause` ごとの総試行回数と成功回数、修正タイプ別の成功数を `fix_stats` に記録。
2. **新規パターン登録**: 修正が成功（`success=True`）かつ新しいエラーメッセージの場合、ベクトル化してインデックスに追加。

#### 3. ログからの自律学習 (`learn_from_session_logs`)
1. ログ内の `SESSION_COMPLETED` イベントやパイプライン履歴を走査。
2. 「テスト失敗分析 → コード修正適用 → テスト成功」の成功シーケンスを特定。
3. 成功した修正の組み合わせをナレッジとして抽出。

## 3. Test Cases

### 3.1. Happy Path
- **既知のエラーへの対応**: 過去に解決済みの "NullReferenceException" と類似したメッセージが入力された場合、正しい修正方針（`add_null_validation` 等）が返されること。
- **成功体験の自動学習**: 正常な修正シーケンスを含むログを読み込ませた後、新しいパターンが知識ベースに追加されていること。
- **統計に基づく優先度**: 同一の原因に対し複数の修正方針がある場合、成功率（統計）が高い方が優先的に提案されること（将来拡張）。

### 3.2. Edge Cases
- **類似度が低い場合**: どの過去事例とも似ていない全く新しいエラーが入力された場合、`None` を返し、誤った提案を避けること。
- **負のフィードバックの適用**: 過去に失敗した型変換（`int -> string` 等）が `negative_feedbacks` に記録されている場合、ペナルティが正しく取得でき、スコアリングに反映されること。

## 4. Dependencies
- **Internal**: `SemanticSearchBase`, `VectorEngine`, `MorphAnalyzer`
- **External**: `numpy`, `json`, `datetime`
