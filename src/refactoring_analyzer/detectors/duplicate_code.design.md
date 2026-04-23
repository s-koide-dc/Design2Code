# DuplicateCodeDetector Design Document

## 1. Purpose
`DuplicateCodeDetector` は、コードベース内の重複箇所を検出し、DRY原則の維持を支援します。

## 2. Structured Specification

### Input
- **content**: ソースコード。

### Core Logic
1.  **汎用解析 (`detect`)**: 
    - 空行とコメントを除いた各行をトークン化。
    - 10文字以上の行が 3回以上 出現する場合を「重複」とみなして抽出。
2.  **Roslyn解析 (`detect_roslyn`)**: 
    - Roslyn メトリクスの `bodyHash` (メソッドの中身のハッシュ値) を使用。
    - プロジェクト全体で同一の `bodyHash` を持つメソッドを検索し、完全に一致する重複メソッドを特定。
    - 検出効率を上げるため、同一ハッシュのグループ内で最初のメソッドのみが報告主体となり、他の重複箇所は `occurrences` リストに集約される。
3.  **結果の集約**: 重複している箇所（ファイル名、メソッド名、行番号）をリスト化して報告。

### Test Cases
- **Happy Path**: 完全に同じコードを持つ 2つの C# メソッドが、Roslyn 解析を通じて重複として検出されること。
