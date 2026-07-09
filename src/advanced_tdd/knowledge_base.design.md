# RepairKnowledgeBase Design Document

## 1. Purpose (Updated 2026-02-10 10:45)
`RepairKnowledgeBase` は、テスト修復のための知識ベースです。過去の「明示された失敗原因」と「成功した修正方針」のペアを蓄積し、同じ `root_cause` に対する成功実績から修復アクションを選択します。

`SemanticSearchBase` は保存互換と既存ベクトルインデックス維持のために継承しますが、修正方針の選択ではエラーメッセージの類似度スコアを使用しません。

## 2. Structured Specification

### 2.1. 知識の構造
データは `resources/repair_knowledge.json` に永続化され、意味ベクトルは `resources/vectors/vector_db/repair_knowledge_vectors.npy` に保存されます。
`repair_knowledge_meta.json` / `repair_knowledge_vectors.npy` は `ConfigManager.storage_dir`（`resources/vectors/vector_db`）へ統一し、旧配置（workspace root / `resources` / `cache`）のファイルは初期化時に移行されます。
`ConfigManager` が渡される場合は `workspace_root` と `repair_knowledge_path` もそこから決定し、TDD 本体・対話パイプライン・自律学習で同じ保存先を共有します。

- **Patterns**:
    - `error_signature`: エラーを識別する安定文字列。正規表現として評価しません。
    - `error_message_regex`: 旧データ互換フィールド。読み込み時に `error_signature` へ正規化し、新規判定では参照しません。
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
- `fix_direction` (str | None): 明示された `root_cause` に対して最も成功回数が多い修正方針。

### 2.3. Core Logic

#### 1. 方針取得 (`get_best_fix_direction`)
1. **明示原因の参照**:
   - `root_cause` が空、または未学習の場合は `None` を返す。
   - `error_message` は互換引数として受け取るが、類似検索・キーワード判定には使わない。
2. **成功実績による決定**:
   - `fix_stats[root_cause].fixes` のうち、正の成功回数が最も多い `fix_direction` を返す。
   - 同一原因の成功実績がない場合は `None` を返し、誤った類似提案を避ける。

#### 2. 成功体験の学習 (`add_repair_experience`)
1. **統計更新**: `root_cause` ごとの総試行回数と成功回数、修正タイプ別の成功数を `fix_stats` に記録。
2. **新規パターン登録**: 修正が成功（`success=True`）かつ新しい `error_signature` の場合、既存保存形式との互換のため安定 ID を付与してベクトルインデックスにも追加する。保存時は移行期間中のみ `error_message_regex` も併記する。
3. **負の知識の保持**: 型変換失敗や未解決シンボルは `negative_feedbacks` / `unresolved_symbols` として保持する。修正方針選択ではスコアペナルティとしては使用しない。

#### 3. ログからの自律学習 (`learn_from_session_logs`)
1. ログ内の `SESSION_COMPLETED` イベントやパイプライン履歴を走査。
2. 「テスト失敗分析 → コード修正適用 → テスト成功」の成功シーケンスを特定。
3. 成功した修正の組み合わせをナレッジとして抽出。
4. `pipeline_*.json` の JSON Lines 形式と単一 JSON 形式の両方を許容し、ログ形式の差異で学習を止めない。
5. 不正なJSON行はファイル名と行番号をwarningへ記録してスキップし、ログ内容自体は診断へ出力しない。

#### 4. 旧ベクトル配置の移行 (`_migrate_legacy_vector_store_files`)
1. workspace root / `resources` / `cache` に残っている旧 `repair_knowledge_meta.json` / `repair_knowledge_vectors.npy` を探索。
2. 統一保存先 `storage_dir` に新しいファイルがなければ移動し、すでに存在する場合は新しい方を優先してコピーまたは旧ファイル削除を行う。
3. 移行失敗は初期化を止めず、通常のロードへフォールバックする。

## 3. Test Cases

### 3.1. Happy Path
- **既知の原因への対応**: 過去に解決済みの `root_cause` が入力された場合、成功回数が最も多い修正方針（`add_null_validation` 等）が返されること。
- **成功体験の自動学習**: 正常な修正シーケンスを含むログを読み込ませた後、新しいパターンが知識ベースに追加されていること。
- **統計に基づく優先度**: 同一の原因に対し複数の修正方針がある場合、成功回数が多い方が優先的に提案されること。

### 3.2. Edge Cases
- **未学習の原因**: `root_cause` に対応する成功実績がない場合、エラーメッセージが既存パターンに似ていても `None` を返すこと。
- **負のフィードバックの保持**: 過去に失敗した型変換（`int -> string` 等）が `negative_feedbacks` に記録されている場合、ペナルティ情報が取得できること。

## 4. Dependencies
- **Internal**: `SemanticSearchBase`, `VectorEngine`, `MorphAnalyzer`
- **External**: `numpy`, `json`, `datetime`

## 5. Review Notes
- 2026-06-09: repair knowledge のベクトルDB保存先統一、旧配置ファイル移行、`ConfigManager` 優先の metadata path 解決、および `pipeline_*.json` ログ学習の現行挙動に合わせて更新。
- 2026-06-25: `knowledge_base.py` の現行実装を再確認。旧配置ファイル移行、`ConfigManager` 優先の保存先解決、`pipeline_*.json` / `SESSION_COMPLETED` ログ学習、負のフィードバックと未解決シンボル保持の設計記述が実装と一致していることを確認した。
- 2026-06-25: 成功体験追加時の repair pattern ID 付与と、現行 `SemanticSearchBase.add_item(item, vector)` API に合わせた index 登録を反映。検索説明も実装に合わせてベクトル検索中心へ更新。`save_knowledge` は wrapper metadata と `LightVectorCollection` 側の items/index を同期して保存する。
- 2026-06-29: JSON Linesの不正行に対する診断契約を反映。
- 2026-06-30: 自動修正の回帰検証後に実装との同期を再確認。
- 2026-07-07: 修正方針選択からベクトル類似度スコア閾値を除去し、明示 `root_cause` の成功統計に基づく決定へ変更。ベクトル保存は互換目的で維持。
- 2026-07-07: `error_message_regex` を互換フィールドへ降格し、内部のエラー識別子を `error_signature` へ移行。
- 2026-07-08: .NET 10 stable SDK 化、構造的修復フロー、Roslyn 検査モード追加後の全体検証に合わせて再同期。`RepairKnowledgeBase` は修正方針選択で引き続き明示 `root_cause` の成功統計のみを使用し、エラーメッセージ類似度やキーワード判定へフォールバックしない。
