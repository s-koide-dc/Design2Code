# EventProcessor Design Document

## 1. Purpose
`EventProcessor` は、AIシステムのリアルタイムイベント（Fast Path）を処理するモジュールです。対話セッションの完了、アクションやテストの失敗、ユーザーからのフィードバックなどのイベントを捕捉し、即時的な学習や知識の蓄積、および将来の分析のためのキュー保存を担当します。

## 2. Structured Specification

### 2.1. イベント処理フロー (`process_event`)
- **Input**:
  - `event_type` (str): イベントの種類（'SESSION_COMPLETED', 'USER_FEEDBACK', 'TEST_FAILED'等）
  - `data` (dict): イベントに付随する詳細データ
- **Logic**:
  1. イベントごとにユニークな `event_id` を生成し、タイムスタンプを付与します。
  2. `logs/learning_queue/` ディレクトリに、生イベントデータをJSON形式で保存します（バッチ学習用）。
  3. イベントタイプに応じて、以下の即時処理をディスパッチします。
     - **SESSION_COMPLETED**: 明確化履歴の確認、および成功した修復タスクからのナレッジ抽出。
     - **USER_FEEDBACK**: 明示された用語マッピングまたは振る舞いフィードバックの永続化。
     - **TEST_FAILED / ACTION_FAILED**: 失敗イベントを構造化し、将来の分析用に記録する。

### 2.2. 学習ロジック
- **修復ナレッジの抽出**: 
  - セッション中に `RECOVERY_FROM_TEST_FAILURE` タスクが成功した場合、`RepairKnowledgeBase` を通じてその解決策を即座にインデックス化します。
- **ユーザーフィードバックの解析**:
  - `terminology_mapping.source` / `terminology_mapping.target` が明示された場合だけ専門用語の対応関係として扱います。
  - 抽出された用語は `learned_mappings.jsonl` に追記され、振る舞いに関するフィードバックは `behavioral_feedback.jsonl` に保存されます。
- **失敗イベントの記録**:
  - `TEST_FAILED` / `ACTION_FAILED` は `analysis` / `analysis_result.analyses` / `action_result.analysis_result.analyses` / `exception` などの構造化フィールドから `error_type`、`root_cause`、対象ファイル・メソッド、メッセージを正規化します。
  - 正規化した失敗は `logs/failure_events.jsonl` に追記します。
  - `RepairKnowledgeBase` が利用可能で、`error_type` が明示されている場合は、成功修復ではない観測として `add_repair_experience(success=False)` に渡し、根本原因別の発生統計を更新します。
  - `RepairKnowledgeBase` への記録に失敗してもイベント受理は失敗させず、警告ログに留めます。

## 3. Dependencies
- `RepairKnowledgeBase`: 修復パターンの蓄積
- `logging`, `json`, `hashlib`, `pathlib`: 基本機能
