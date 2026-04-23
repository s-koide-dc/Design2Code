# PythonRefactoringAnalyzer Design Document

## 1. Purpose
`PythonRefactoringAnalyzer` は、Python プロジェクトに対して AST (抽象構文木) と正規表現を併用したリファクタリング分析を提供します。

## 2. Structured Specification

### Core Logic
1.  **ファイル検索**: `venv` や `__pycache__` を除外し、`.py` ファイルを収集。
2.  **検出器の初期化**: `LongMethodDetector`, `DuplicateCodeDetector`, `ComplexConditionDetector` を使用。
3.  **分析の実行**: 各ファイルに対して `_safe_analyze_file` を実行。`LongMethodDetector` 等は内部で Python 特有の AST 解析を使用する。

## 3. Dependencies
- **Internal**: 
  - `base_analyzer`: 基底分析機能
  - `long_method`: 長いメソッドの検出
  - `duplicate_code`: 重複コードの検出
  - `complex_condition`: 複雑な条件式の検出
- **External**: `os`