# text_parser Design Document

## 1. Purpose

`text_parser` はテキストから URL、SQL パラメータ、引用符リテラル、数値を抽出する。

## 2. Structured Specification

### Input
- **Description**: 対象テキスト。
- **Type/Format**: `str | None`
- **Example**: `"SELECT * FROM Users WHERE Id=@id"`

### Output
- **Description**: 抽出結果（URL配列、パラメータ配列、数値、真偽など）。
- **Type/Format**: `List[str]` / `Optional[str]` / `Optional[int]` / `bool`

### Core Logic
1. `extract_urls` はトークン化し、`http/https/www` を URL として返す。
2. `extract_sql_params` は `@` で始まる識別子を抽出する。
3. `extract_quoted_literals` は各種引用符ペアからリテラルを抽出する。
4. `contains_word` は単語境界を考慮して含有判定する。
5. `is_numeric_literal` は整数/小数を判定する。
6. `extract_percentage_value` は `%` 付き数値を返す。
7. `extract_decimal_value` は小数表記を抽出する。

### Test Cases
- **Happy Path**:
  - **Scenario**: `http://example.com` を含む。
  - **Expected Output**: URL が抽出される。
- **Edge Cases**:
  - **Scenario**: 空文字。
  - **Expected Output / Behavior**: 空配列または `None` を返す。

## 3. Dependencies
- **Internal**: `utils`
