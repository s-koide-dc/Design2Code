# ApprovalMessageGenerator Design Document

## 1. Purpose
`ApprovalMessageGenerator` は、ユーザーにアクションの実行許可を求める際の承認メッセージを、タスクの種類やパラメータに応じて動的に生成します。

## 2. Structured Specification

### Input
- **task_name**: タスク名。
- **parameters**: タスクの引数（ファイル名、コマンド等）。
- **task_definitions**: タスクごとのテンプレート定義。

### Core Logic
1.  **テンプレートの選択**: 
    - 複合タスク全体 (`COMPOUND_TASK_OVERALL`) またはクリティカルな個別ステップ (`CRITICAL_SUBTASK`) 用のテンプレートを選択。
    - `task_definitions.json` に定義がある場合はそれを優先。
2.  **プレースホルダーの置換**: 
    - テンプレート内の `{filename}`, `{command}` 等を実際のパラメータ値で置換。
3.  **フォールバック**: 
    - パラメータ不足や定義不在時は、汎用的なデフォルトメッセージを生成。

## 3. Dependencies
- **External**: `json`, `os`
