# GodClassDetector Design Document

## 1. Purpose
`GodClassDetector` は、外部の構造解析または設計判断で明示された `god_class` fact をコードスメルとして報告します。

## 2. Structured Specification

### Input
- **Python source**: `@refactoring_fact("god_class")` が付与されたクラス定義。
- **C# Roslyn details**: クラスまたは構造体の `refactoringFacts` に含まれる `god_class`。

### Core Logic
1. Python は AST でクラス定義とデコレータ構造を読む。
2. C# は Roslyn が出力した `refactoringFacts` を読む。
3. 行数、メソッド数、テキストパターン、しきい値から `god_class` を推定しない。
4. 対応する構造解析結果がない入力では検出せず、必要に応じて diagnostics に `STRUCTURAL_ANALYSIS_REQUIRED` を残す。

### Output
- `type`: `god_class`
- `severity`: `high`
- `metrics.structural_facts`: `["god_class"]`

### Test Cases
- `@refactoring_fact("god_class")` 付き Python クラスが検出される。
- fact のない Python クラスは検出されない。
- Roslyn のクラス詳細に `refactoringFacts: ["god_class"]` がある場合だけ検出される。
