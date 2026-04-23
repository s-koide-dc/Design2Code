# CSharpRefactoringAnalyzer Design Document

## 1. Purpose
`CSharpRefactoringAnalyzer` は、C# プロジェクトに対して Roslyn 解析結果を活用した高度なリファクタリング分析を提供します。

## 2. Structured Specification

### Input
- **project_path**: C# プロジェクトのパス。

### Output
- **analysis_result**: スメルリスト、解析済みファイル数、Roslyn 構造化データ。

### Core Logic
1.  **Roslyn解析の実行**: `ActionExecutor` を通じて `MyRoslynAnalyzer` を呼び出し、構造化されたコード情報を取得。
2.  **検出器の実行**: 取得した `details_by_id`（クラス・メソッド詳細）をループ処理。
    - **Class**: `GodClassDetector` を実行。
    - **Method**: `LongMethodDetector`, `ComplexConditionDetector`, `DuplicateCodeDetector` を実行。
3.  **結果の統合**: 検出されたすべてのスメルを一つのリストに集約して返す。

## 3. Dependencies
- **Internal**: `base_analyzer`, `detectors`, `action_executor`
- **External**: `os`