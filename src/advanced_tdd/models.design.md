# TDD Models Design Document

## 1. Purpose
`models` モジュールは、高度な TDD サイクルで使用される標準的なデータ構造（データクラス）を定義し、モジュール間での情報の受け渡しを円滑にします。

## 2. Structured Specification

### 2.1. 主要データクラス

- **`TestFailure`**:
    - `test_file`, `test_method`: 失敗の場所。
    - `error_type`, `error_message`: エラーの分類と内容。
    - `stack_trace`: 完全なスタックトレース。
    - `line_number`: 発生行。

- **`CodeFixSuggestion`**:
    - `id`, `type`: 提案の識別子と種類。
    - `priority`, `description`: 優先度と解説。
    - `current_code`, `suggested_code`: コード断片。
    - `safety_score`: 安全性スコア。
    - `auto_applicable`: 自動適用フラグ。

- **`TDDGoal`**:
    - `description`: 目標概要。
    - `acceptance_criteria`: 受入基準のリスト。
    - `priority`, `estimated_effort`: 属性情報。

## 3. Dependencies
- `dataclasses`, `typing`