# DuplicateCodeDetector Design Document

## 1. Purpose
`DuplicateCodeDetector` は、構造解析または設計判断で明示された重複グループをコードスメルとして報告します。

## 2. Structured Specification

### Input
- **Python source**: `@duplicate_group("group-id")` が付与された関数定義。
- **C# Roslyn details**: メソッド詳細の `duplicateGroupId`。

### Core Logic
1. Python は AST で関数定義と `duplicate_group` デコレータを読む。
2. C# は Roslyn が `DuplicateGroupAttribute` から出力した `duplicateGroupId` を読む。
3. 同じ group id が2箇所以上に現れた場合だけ、1件の `duplicate_code` として集約する。
4. 行テキスト一致、正規表現、文字数、出現回数しきい値、body hash から重複を推定しない。

### Output
- `type`: `duplicate_code`
- `severity`: `medium`
- `duplicate_group_id`: 明示された group id
- `metrics.occurrences_count`: 同一 group の出現数

### Test Cases
- 同じ `@duplicate_group("...")` を持つ2つの Python 関数が1件の重複として報告される。
- group id が単独の関数は報告されない。
- Roslyn の `duplicateGroupId` が同じ2つの C# メソッドが1件の重複として報告される。
