# ApprovalWorkflow Design Document

## 1. Purpose

ApprovalWorkflow は TaskManager の承認応答に共通する値の正規化と承認履歴の記録を担当する。
タスクの状態遷移やキャンセル判断そのものは TaskManager に残す。

## 2. Structured Specification

### Input

- **Description**: intent、user_response entity、対象 task、承認結果。
- **Type/Format**: str, dict

### Output

- **Description**: 正規化された user response、または task に追加された approval history。
- **Type/Format**: Any / None

### Core Logic

1. 直接の agree/disagree intent を承認結果へ変換する。
2. entity に含まれる user_response を優先して取得する。
3. task の approval_history を初期化し、承認・拒否の記録を共通形式で追加する。
4. 実際の state transition、再評価、キャンセルは呼び出し側へ返す。

## 3. Test Cases

- agree intent が approved value へ変換される。
- disagree intent が rejected value へ変換される。
- entity 由来の応答が利用される。
- approval history に timestamp、action、task 情報が記録される。

