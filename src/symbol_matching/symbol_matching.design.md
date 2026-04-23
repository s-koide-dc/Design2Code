# symbol_matching Design Document

## 1. Purpose

`symbol_matching` は日本語指示とコードシンボルの対応付けを行う。  
`SymbolMatcher` を通じて意味的類似度とドメイン辞書を利用したマッチングを提供する。

## 2. Structured Specification

### Input
- **Description**: 検索文と候補シンボル。
- **Type/Format**: `str`, `List[str]`

### Output
- **Description**: 最適なシンボル名と類似度。
- **Type/Format**: `Tuple[str | None, float]`

### Core Logic
1. `SymbolMatcher` がドメイン辞書を読み込む。
2. `find_best_match` は候補の中から意味的に一致するものを選択する。
3. `calculate_semantic_similarity` で文とシンボルの類似度を計算する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 候補に適切なシンボルが含まれる。
  - **Expected Output**: そのシンボルが返る。
- **Edge Cases**:
  - **Scenario**: `vector_engine` が未設定。
  - **Expected Output / Behavior**: マッチ無しで `None` を返す。

## 3. Dependencies
- **Internal**: `symbol_matcher`
