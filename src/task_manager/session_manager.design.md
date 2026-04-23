# session_manager Design Document

## 1. Purpose

`SessionManager` はセッション単位のタスク状態を管理し、統計と整合性検証を提供する。

## 2. Structured Specification

### Input
- **Description**: アクティブタスク辞書、最終活動時刻辞書、設定オブジェクト。
- **Type/Format**: `dict`, `dict`, `Config`

### Output
- **Description**: セッション統計、タスク状態、整合性検証結果。
- **Type/Format**: `dict`

### Core Logic
1. `update_activity` で `session_last_activity` を更新する。
2. `get_session_id` は `session_id:` プレフィックスから ID を抽出し、無ければ既定値を返す。
3. `get_stats` はアクティブ数と設定上限を返す。
4. `get_task_state` はタスク情報と複合タスクの進捗をまとめる。
5. `get_memory_usage_stats` はタスク数と推定メモリ使用量を返す。
6. `validate_integrity` は必須項目・タスク定義・サブタスク整合性を検証する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 有効なセッションとタスク。
  - **Expected Output**: `valid=true` で状態が返る。
- **Edge Cases**:
  - **Scenario**: タスク定義が無い。
  - **Expected Output / Behavior**: `issues` に不整合が記録される。

## 3. Dependencies
- **Internal**: `config_manager`
- **External**: `time`, `sys`
