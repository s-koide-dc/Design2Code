# SymbolMatcher Design Document

## 1. Purpose

`SymbolMatcher` は自然言語文とコードシンボルの一致判定を行う。  
形態素解析で抽出した語とシンボル名のトークンをベクトル化し、類似度で候補を選択する。

## 2. Structured Specification

### Input
- **Description**: 文、候補シンボル、ドメイン辞書。
- **Type/Format**: `str`, `List[str]`, `Dict[str, List[str]]`

### Output
- **Description**: 最適なシンボル名と類似度。
- **Type/Format**: `Tuple[str | None, float]`

### Core Logic
1. `domain_dictionary.json` と `knowledge_base` からドメイン語彙を読み込む。
2. `extract_keywords` で文からキーワードを抽出し、ドメイン語彙で展開する。
3. `tokenize_symbol` でシンボル名をトークン化する。
4. `calculate_semantic_similarity` で文とシンボルの類似度を計算する。
5. `find_best_match` は候補をフィルタし、類似度と決定的な優先順で 1 件を選ぶ。

### Test Cases
- **Happy Path**:
  - **Scenario**: 文に対応する候補が存在する。
  - **Expected Output**: 対応するシンボル名が返る。
- **Edge Cases**:
  - **Scenario**: `vector_engine` が未設定。
  - **Expected Output / Behavior**: ドメイン語彙とトークン一致のみで判断する。

## 3. Dependencies
- **Internal**: `morph_analyzer`, `vector_engine`
- **External**: `json`, `os`
