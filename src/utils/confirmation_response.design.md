# confirmation_response Design Document

## 1. Purpose

`confirmation_response` は承認フローで共有する意図名と遷移名の定数を一元管理する。  
`AGREE` / `DISAGREE` / `CLARIFICATION_RESPONSE` や `AGREED` / `DISAGREED` を共通化し、複数モジュールでの生文字列比較を避ける。

## 2. Structured Specification

### Input
- **Description**: なし。定数定義のみを提供する。
- **Type/Format**: N/A

### Output
- **Description**: 承認応答用の文字列定数。
- **Type/Format**: `str`

### Core Logic
1. `INTENT_CLARIFICATION_RESPONSE` は明示的な確認応答インテント名を表す。
2. `INTENT_AGREE` / `INTENT_DISAGREE` は承認 / 拒否のインテント名を表す。
3. `RESPONSE_APPROVED` / `RESPONSE_REJECTED` は `user_response` に保存する正規化済み値を表す。
4. `STATE_AGREED` / `STATE_DISAGREED` は確認応答タスク定義の遷移先状態を表す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 複数モジュールが承認・拒否判定に同じ定数を利用する。
  - **Expected Output**: 表記揺れなく同一値で比較できる。

## 3. Dependencies
- **Internal**: なし
- **External**: なし
