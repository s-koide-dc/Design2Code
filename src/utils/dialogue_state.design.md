# dialogue_state Design Document

## 1. Purpose

`dialogue_state` は対話パイプラインで共有する状態名定数を一元管理する。  
`pending_confirmation`、`task_clarification`、`feedback_collection` のような状態識別子を共通化し、複数モジュールでの文字列直書きを避ける。

## 2. Structured Specification

### Input
- **Description**: なし。定数定義のみを提供する。
- **Type/Format**: N/A

### Output
- **Description**: 対話状態名の文字列定数。
- **Type/Format**: `str`

### Core Logic
1. `PENDING_CONFIRMATION` は明示承認待ち状態を表す。
2. `TASK_CLARIFICATION` はタスク由来の補足質問状態を表す。
3. `FEEDBACK_COLLECTION` は訂正フィードバック収集中の状態を表す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 他モジュールが状態定数を import して比較に使う。
  - **Expected Output**: 文字列の表記揺れなく同一値で比較できる。

## 3. Dependencies
- **Internal**: なし
- **External**: なし
