# BaseRefactoringAnalyzer Design Document

## 1. Purpose
`BaseRefactoringAnalyzer` は、特定言語に依存しないリファクタリング分析の基底機能を提供します。ファイルの読み込み、除外ルールの適用、および共通の分析フローを管理します。

## 2. Structured Specification

### Input
- **project_path**: 分析対象のプロジェクトパス。
- **options**: 分析オプション（除外ルール等）。

### Output
- **smells**: 検出されたコードスメルのリスト。

### Core Logic
1.  **初期化**: 各言語特有の `smell_detectors` を初期化（サブクラスで実装）。
2.  **ファイルスキャン**: プロジェクト内のファイルを再帰的に探索し、`_should_exclude_file` で除外対象をフィルタリング。除外ルールは `exclusion_rules`（`file_patterns`, `directory_patterns`, `content_patterns`）に基づく。
3.  **安全な分析 (`_safe_analyze_file`)**: 
    - **ファイルサイズチェック**: 10MBを超えるファイルはパフォーマンス維持のためスキップ。
    - **堅牢な読み込み**: `utf-8`, `utf-8-sig`, `cp1252`, `latin1` の順でデコードを試行。
    - **エラー分離**: 個別の検出器の例外が全体の分析を停止させないよう、各検出器の実行を `try-except` で保護し、結果を集約。

## 3. Dependencies
- **Internal**: 
  - `long_method`: 長いメソッドの検出
  - `duplicate_code`: 重複コードの検出
  - `complex_condition`: 複雑な条件式の検出
  - `god_class`: 神クラスの検出
- **External**: `os`, `fnmatch`
