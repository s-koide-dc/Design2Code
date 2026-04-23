# LongMethodDetector Design Document

## 1. Purpose
`LongMethodDetector` は、推奨される行数を超えている「長いメソッド」を検出します。

## 2. Structured Specification

### Input
- **content**: ソースコード。
- **thresholds**: `long_method_lines`（デフォルト: 20行）。

### Core Logic
1.  **言語判定**: ファイル拡張子に基づき解析手法を選択。
2.  **Python解析 (`_detect_python_long_methods`)**: 
    - `ast` モジュールを使用して関数定義ノード（`FunctionDef`）を抽出。
    - 装飾子や空行を除いた実質的なコード行数をカウント。
3.  **汎用解析 (`_detect_generic_long_methods`)**: 
    - 正規表現でメソッド定義を特定。
    - 波括弧 `{}` のレベル（`brace_level`）を追跡してメソッドの境界を特定。
4.  **Roslyn解析 (`detect_roslyn`)**: 
    - Roslyn メトリクスの `lineCount` を直接使用して判定。
    - メソッドの開始・終了行（`startLine`, `endLine`）に基づき、正確なコード範囲を特定。
5.  **閾値判定**: カウントされた行数が閾値を超えた場合、スメル（severity: medium/high）として登録。警告レベルは 2倍の行数を超える場合に high と判定。

### Test Cases
- **Happy Path**: 30行のメソッドが閾値20の設定で正しく検出されること。
- **Edge Case**: Python の docstring が行数にカウントされないこと（AST版）。
