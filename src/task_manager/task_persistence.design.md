# TaskPersistence Design Document

## 1. Purpose
`TaskPersistence` は、タスクの状態を JSON ファイルとして保存・読み込みすることで、プロセスの再起動後も対話を継続できるようにします。

## 2. Structured Specification

### Core Logic
1.  **状態の保存 (`save_task_state`)**: 
    - セッション ID ごとに `task_state_{id}.json` を作成。
    - タイムスタンプとバージョン情報を付与してシリアライズ。
2.  **状態の復元 (`load_task_state`)**: 
    - 指定された ID のファイルを読み込み。
    - 最大保持時間（`max_age_hours`）を超えた古い状態は破棄。
3.  **自動クリーンアップ**: 
    - 定期的にストレージディレクトリをスキャンし、期限切れのファイルを削除。

## 3. Dependencies
- **External**: `json`, `os`, `datetime`
