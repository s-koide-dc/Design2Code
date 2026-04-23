# validation_renderer Design Document

## 1. Purpose

`validation_renderer` は DTO バリデーションルールからガード行を生成する。

## 2. Structured Specification

### Input
- **Description**: DTO 名、変数名、ルール定義、フィールド型、テンプレート、戻りアクション。
- **Type/Format**: `str`, `dict`
- **Example**:
  ```json
  {
    "dto_name": "OrderCreateRequest",
    "validation_rules": { "OrderCreateRequest.Total": ["min_value=1"] }
  }
  ```

### Output
- **Description**: ガード行の配列。
- **Type/Format**: `List[str]`
- **Example**: `["if (req.Total < 1) return BadRequest();"]`

### Core Logic
1. `validation_rules` から対象 DTO に一致するキーを抽出する。
2. ルール種別（required/max_len/min_len/contains/min_value/max_value）ごとにテンプレートを選ぶ。
3. テンプレートの `{Var}/{Field}/{Max}` などを置換してガード行を生成する。
4. `return_action` が `return null;` 以外の場合、戻り式を差し替える。
5. コントローラ用ガードでは `var_name` が存在する場合に `null` チェックを先頭に追加する。

### Test Cases
- **Happy Path**:
  - **Scenario**: `required` と `min_value` を含む。
  - **Expected Output**: 2 つ以上のガード行が生成される。
- **Edge Cases**:
  - **Scenario**: DTO が一致しないルールのみ。
  - **Expected Output / Behavior**: 空配列が返る。

## 3. Dependencies
- **Internal**: なし
