# calc_ops Design Document

## 1. Purpose

`calc_ops` は `CALC` ノードを具体的な C# 計算・更新・集計文へ変換する。  
現在は `entity_resolution` に応じて concretization の強さを変え、曖昧な entity 解決では cross-entity fallback を禁止する。

## 2. Structured Specification

### Input
- **Description**: `ActionSynthesizer`、`CALC` ノード、現在の path。
- **Type/Format**: `Dict[str, Any]`, `Dict[str, Any]`

### Output
- **Description**: 計算ステートメントを含む path 候補。
- **Type/Format**: `List[Dict[str, Any]]`

### Core Logic
1. `semantic_roles.ops` に `aggregate_by_product` がある場合は CSV 集計専用ロジックへ分岐する。
2. `entity_resolution` を読み、以下の方針を決める。
   - `unique_owner` / `explicit_entity`: 通常 concretization を許可する。
   - `history_fallback`: exact target に閉じた fallback のみ許可する。
   - `ambiguous`: cross-entity fallback を禁止する。
3. target property / target hint / logic goals から assignment target を決める。
4. `datetime` hint, `%`, quantity/price, rate rules, aggregation/update intent を考慮して式を組み立てる。
5. 曖昧解決で安全に target を決められない場合は property assignment を作らず、明示 TODO 停止へ寄せる。
6. 集計では accumulator 変数を生成し、path に登録する。

### Test Cases
- **Happy Path**:
  - **Scenario**: unique owner を持つ `DiscountedPrice` 計算。
  - **Expected Output**: owner entity の property assignment が生成される。
- **Edge Cases**:
  - **Scenario**: ambiguous owner の `Total` 計算。
  - **Expected Output / Behavior**: cross-entity fallback を行わず TODO 停止する。

## 3. Dependencies
- **Internal**:
  - `action_utils`
  - `text_parser`
- **External**: なし
