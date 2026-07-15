# TaskStateStore Design Document

## 1. Purpose

TaskStateStore は TaskManager と TaskPersistence の境界を提供する。
永続化の有効・無効判定をタスク状態遷移から分離し、TaskManager が保存方式の詳細へ依存しないようにする。

## 2. Structured Specification

### Input

- **Description**: 永続化フラグ、保存先、状態保持時間、ログ管理オブジェクト。
- **Type/Format**: bool, str, int, LogManager | None

### Output

- **Description**: タスク状態の保存・復元・削除・期限切れクリーンアップを提供する store。
- **Type/Format**: TaskStateStore

### Core Logic

1. 永続化無効時は内部 persistence を生成しない。
2. 永続化有効時だけ TaskPersistence を生成する。
3. 保存・復元・削除・クリーンアップを内部 persistence へ委譲する。
4. 無効時の操作は副作用を起こさず、保存は false、復元は None を返す。

## 3. Test Cases

- 永続化有効時に TaskPersistence が生成される。
- 永続化無効時にファイル操作が発生しない。
- 各操作が内部 persistence へ委譲される。

