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
     - **USER_FEEDBACK**: 用語マッピング（「AはBの意味」等）の抽出と永続化。
     - **TEST_FAILED / ACTION_FAILED**: 失敗パターンの記録（将来の分析用）。

### 2.2. 学習ロジック
- **修復ナレッジの抽出**: 
  - セッション中に `RECOVERY_FROM_TEST_FAILURE` タスクが成功した場合、`RepairKnowledgeBase` を通じてその解決策を即座にインデックス化します。
- **ユーザーフィードバックの解析**:
  - 正規表現（`「(.+?)」\s*は\s*(.+?)\s*の[こと|意味]`）を用いて、ユーザーが教えた専門用語の対応関係を抽出します。
  - 抽出された用語は `learned_mappings.jsonl` に追記され、振る舞いに関するフィードバックは `behavioral_feedback.jsonl` に保存されます。

## 3. Dependencies
- `RepairKnowledgeBase`: 修復パターンの蓄積
- `logging`, `json`, `re`, `pathlib`: 基本機能
