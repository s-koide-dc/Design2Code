# TaskManagerMetrics Design Document

## 1. Purpose
`TaskManagerMetrics` は、タスクの実行時間、状態遷移数、承認要求回数などの統計情報を収集し、システムのパフォーマンスと利用状況を可視化します。

## 2. Structured Specification

### Core Logic
1.  **イベント記録**: 
    - `start_task`: タスク開始時刻と種別を記録し、開始カウンターをインクリメント。
    - `record_state_transition`: 状態遷移（例: "PENDING -> RUNNING"）を履歴に追加。
    - `record_approval_request`: ユーザー承認要求の発生回数をカウント。
    - `record_interruption`: 割り込み発生回数をカウント。
2.  **完了処理**: 
    - `complete_task`: 終了時刻を記録し、`duration`（実行時間）を算出。タスク名ごとの統計（平均、最小、最大時間）を `timing_stats` として更新。
3.  **サマリー生成**: アクティブタスク数、完了タスク数、および全カウンターの合計を辞書形式で出力。
4.  **クリーンアップ**: 
    - `cleanup_stale_tasks`: 指定時間（デフォルト 24時間）を経過したアクティブタスクを自動的に `TIMEOUT` 状態として完了処理。

## 3. Dependencies
- **External**: `time`, `collections`, `dataclasses`
