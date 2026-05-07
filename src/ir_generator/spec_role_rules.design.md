# spec_role_rules Design Document

## 1. Purpose

`spec_role_rules` は runtime intent/role に潰れる前の仕様意味を `spec_role` として固定する。`IR meaning preservation` の基準面を作るための小さな変換層である。

## 2. Structured Specification

### Input
- **Description**: runtime intent、原文、token 列、logic goals、node type、粗い intent/role 推定関数。
- **Type/Format**: `str`, `List[Dict[str, Any]]`, `Callable`

### Output
- **Description**: 仕様意味 role。
- **Type/Format**: `str`

### Core Logic
1. `LOOP` は `ITERATE`、`CONDITION` は `CHECK` を優先する。
2. `FETCH`, `DATABASE_QUERY`, `HTTP_REQUEST`, `FILE_IO` は `FETCH` にまとめる。
3. `JSON_DESERIALIZE` は `DESERIALIZE`、`PERSIST` は `PERSIST`、`DISPLAY` は `DISPLAY`、`RETURN` は `RETURN` に写す。
4. `CALC` は `CALCULATE`、`LINQ` は logic の有無に応じて `FILTER` または `TRANSFORM` に写す。
5. runtime intent が弱い場合は、補助の intent/role 推定関数を使って `CHECK`, `DISPLAY`, `PERSIST`, `FETCH`, `FILTER` を再判定する。
6. どれにも当てはまらない場合は `ACTION` を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: `intent=CALC`。
  - **Expected Output**: `CALCULATE`。
- **Edge Cases**:
  - **Scenario**: `intent=LINQ` だが logic goal が無い。
  - **Expected Output / Behavior**: `TRANSFORM`。

## 3. Dependencies
- **Internal**: なし
- **External**: なし
