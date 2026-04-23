# context_utils Design Document

## 1. Purpose

`context_utils` はコンテキストやテキストから、パス抽出とデバッグ向けサマリー生成を行う。

## 2. Structured Specification

### Input
- **Description**: 文字列またはコンテキスト辞書。
- **Type/Format**: `str` / `dict | None`

### Output
- **Description**: 正規化パス文字列、抽出パス、またはコンテキスト要約辞書。
- **Type/Format**: `str | None` / `dict`

### Core Logic
1. `normalize_path` は引用符の除去・区切り文字の正規化・重複スラッシュ除去を行う。
2. `extract_path_from_text` は引用文字列とトークンから候補を抽出し、パス判定に合致するものを返す。
3. `_get_context_summary` は intent / entities / action / response / error を抽出し、`None` 時は既定の要約を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: パスを含む文字列。
  - **Expected Output**: 正規化されたパスが返る。
- **Edge Cases**:
  - **Scenario**: コンテキストが `None`。
  - **Expected Output / Behavior**: `None` 用の既定サマリーが返る。

## 3. Dependencies
- **External**: `os`
