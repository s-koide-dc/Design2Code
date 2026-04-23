# GodClassDetector Design Document

## 1. Purpose
`GodClassDetector` は、単一責任原則に違反し、多くの機能や状態を持ちすぎている巨大なクラス（神クラス）を検出します。

## 2. Structured Specification

### Input
- **thresholds**: 
    - `class_line_count`（デフォルト: 300行）。
    - `god_class_method_count`（デフォルト: 15個）。

### Core Logic
1.  **汎用解析 (`detect`)**: 
    - クラス定義を特定し、波括弧のバランスからクラスの終端を判定。
    - クラス内の行数とメソッド数をカウント。
2.  **Roslyn解析 (`detect_roslyn`)**: 
    - Roslyn メトリクスの `lineCount` と、メソッドリストの要素数を使用。
    - インターフェースやベースクラスを除いた、純粋なクラス/構造体（`Class`, `Struct`）を対象とする。
3.  **判定基準**: 
    - 行数が 300行 を超える、または メソッド数が 15個 を超える場合に「神クラス」として検出。
    - 判定結果には、具体的な行数とメソッド数、およびそれぞれの閾値が含まれる。

### Test Cases
- **Happy Path**: 400行かつ 20個のメソッドを持つクラスが、高優先度のスメルとして検出されること。
