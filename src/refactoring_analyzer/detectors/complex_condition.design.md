# ComplexConditionDetector Design Document

## 1. Purpose
`ComplexConditionDetector` は、理解が困難でバグの原因となりやすい、複雑すぎる条件分岐（if文の論理演算子の多用等）を検出します。

## 2. Structured Specification

### Input
- **content**: ソースコード。
- **thresholds**: `cyclomatic_complexity`（デフォルト: 6）。

### Core Logic
1.  **汎用解析 (`detect`)**: 
    - `if` 文を含む行を抽出。
    - `&&`, `||`, `==` などの論理・比較演算子の数をカウントし、複雑度（complexity）を算出。
2.  **Roslyn解析 (`detect_roslyn`)**: 
    - Roslyn メトリクスの `cyclomaticComplexity` を直接使用して判定。
    - メソッドの開始行（`startLine`）を特定し、構造化データからの直接抽出により、正規表現よりも正確な位置情報を提供。
3.  **閾値判定**: 複雑度が閾値（デフォルト 6）を超えた場合、スメルとして登録。警告レベル（severity）は閾値の 1.5倍を境に medium/high を切り替える。

### Test Cases
- **Happy Path**: 7つの演算子を含む if 文が、閾値6の設定で正しく検出されること。
