# ComplexConditionDetector Design Document

## 1. Purpose
`ComplexConditionDetector` は、構文木に明示された複合条件構造を検出します。
演算子の文字列出現数や循環的複雑度スコアでは判定しません。

## 2. Structured Specification

### Input
- **content**: Pythonソースコード。
- **Roslyn metadata**: C#メソッドの `conditionStructures`。

### Core Logic
1.  **汎用解析 (`detect`)**: 
    - Python ASTから `If`、`While`、`IfExp`、`Assert` の条件ノードを取得。
    - 異なるBoolean演算子の入れ子、Booleanグループの否定、連鎖比較を構造factとして記録。
    - Python以外のソース文字列は推測せず、`STRUCTURAL_ANALYSIS_REQUIRED`を診断。
2.  **Roslyn解析 (`detect_roslyn`)**: 
    - `conditionStructures[].facts` の許可済み構造factだけを使用。
    - `cyclomaticComplexity`から条件式の複雑さを推測しない。

### Test Cases
- **Python**: `and`の子を持つ`or`条件が`mixed_boolean_operators`として検出されること。
- **C#**: Roslynの明示factが検出され、スコア項目を出力しないこと。
- **Unsupported**: C#文字列を直接渡した場合は検出せず、構造解析要求を診断すること。
