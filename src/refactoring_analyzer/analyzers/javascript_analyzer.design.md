# JavaScriptRefactoringAnalyzer Design Document

## 1. Purpose
`JavaScriptRefactoringAnalyzer` は、JavaScript/TypeScript プロジェクトに対して、正規表現と基底分析器を用いたコードスメル検出を提供します。

## 2. Structured Specification

### Core Logic
1.  **ファイル検索**: `node_modules` や `dist` を除外し、`.js`, `.ts` 等の拡張子を持つファイルを収集。
2.  **検出器の初期化**: `LongMethodDetector`, `ComplexConditionDetector` を使用。
3.  **分析の実行**: 基底クラスの `_safe_analyze_file` を呼び出し、各ファイルのスメルを収集。

## 3. Dependencies
- **Internal**: 
  - `base_analyzer`: 基底分析機能
  - `long_method`: 長いメソッドの検出
  - `complex_condition`: 複雑な条件式の検出
- **External**: `os`