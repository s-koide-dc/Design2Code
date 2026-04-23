# semantic_tags Design Document

## 1. Purpose

`semantic_tags` はドメイン辞書からタグを読み込み、テキストにタグが含まれるか判定する。

## 2. Structured Specification

### Input
- **Description**: Synthesizer、ドメインタグ辞書、テキスト、判定対象タグ。
- **Type/Format**: `Dict[str, List[str]]`, `str`

### Output
- **Description**: タグが含まれるかどうかの真偽値。
- **Type/Format**: `bool`

### Core Logic
1. `domain_dictionary_path` を読み取り、`tags` セクションを取得する。
2. 形態素解析が可能ならトークン化して判定を行う。
3. トークン化できない場合は単純な包含判定にフォールバックする。

### Test Cases
- **Happy Path**:
  - **Scenario**: タグに対応する単語が含まれる。
  - **Expected Output**: `True` が返る。
- **Edge Cases**:
  - **Scenario**: 辞書が無い。
  - **Expected Output / Behavior**: 空辞書または `False` を返す。

## 3. Dependencies
- **Internal**:
  - `config_manager`
  - `morph_analyzer`
