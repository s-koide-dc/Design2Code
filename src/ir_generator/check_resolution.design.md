# check_resolution Design Document

## 1. Purpose

`check_resolution` は `CHECK` 系ノードの意味を、runtime intent とは独立した metadata として固定する。`check_kind`, `check_subject`, `check_operator`, `check_value`, `expected_truth`, `subject_resolution` を決定的に生成する。

## 2. Structured Specification

### Input
- **Description**: ステップ文、token 列、logic goals、source 情報、target entity、node type。
- **Type/Format**: `str`, `List[Dict[str, Any]]`, `List[Dict[str, Any]]`, `Optional[str]`

### Output
- **Description**: `CHECK` metadata。対象外なら空辞書。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. 演算子名は `normalize_check_operator` で C# 比較演算子へ正規化する。
2. `null` を含む場合は `null_check` とし、直前 token から subject を拾って `subject_resolution` を決める。
3. `存在` または quoted literal を含む場合は `exists_check` とし、`source_ref` / `source_kind` を保持する。
4. 比較系 `logic_goals` がある場合は `comparison_check` とし、`check_operator` と `check_value` を埋める。
5. 明示 subject が無い場合は history subject か default subject へ保守的に落とす。
6. 必要に応じて `infer_check_target_entity` で弱い `target_entity` を補正する。

### Test Cases
- **Happy Path**:
  - **Scenario**: `config.json` の存在確認。
  - **Expected Output**: `check_kind=exists_check`, `subject_resolution=quoted_literal`。
- **Edge Cases**:
  - **Scenario**: `user == null`。
  - **Expected Output / Behavior**: `check_kind=null_check`。
  - **Scenario**: 比較 operator が goal 側で来る。
  - **Expected Output / Behavior**: `comparison_check` を返す。

## 3. Dependencies
- **Internal**: `text_parser`
- **External**: なし
