# calc_ops Design Document

## 1. Purpose

`calc_ops` は CALC ノードの実処理を担当し、集計・割引・更新などの数値計算を C# 文へ変換する。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、CALC ノード、現在のパス状態。
- **Type/Format**: `Dict[str, Any]`, `Dict[str, Any]`
- **Example**: `node={"intent":"CALC","semantic_roles":{}}`

### Output
- **Description**: 計算ステートメントを含むパス配列。
- **Type/Format**: `List[Dict[str, Any]]`
- **Example**: `[{"statements":[{"type":"raw","code":"var total = ...;"}]}]`

### Core Logic
1. `semantic_roles.ops` に `aggregate_by_product` がある場合は CSV 集計専用ロジックに分岐する。
2. 対象エンティティ/プロパティを推定し、必要な `var_name` と式を組み立てる。
3. 日時系の `semantic_roles` があれば `DateTime.Now/DateTime.UtcNow` を代入式に用いる。
4. 数量・価格ヒントを使って `price * quantity` の式を構成する。
5. ％表現がある場合は `base * (percent/100)` に変換する。
6. 集計意図の場合は累積変数を生成し加算式を作成する。
7. 更新意図または既知状態プロパティの場合はプロパティ代入を行う。
8. それ以外は計算結果をローカル変数として生成する。

### Test Cases
- **Happy Path**:
  - **Scenario**: `price * quantity` の計算。
  - **Expected Output**: 乗算式が生成される。
- **Edge Cases**:
  - **Scenario**: 対象プロパティが特定できない。
  - **Expected Output / Behavior**: 既定の数値プロパティが参照される。

## 3. Dependencies
- **Internal**:
  - `code_synthesis`
  - `action_utils`
  - `text_parser`
