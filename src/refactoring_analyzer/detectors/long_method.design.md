# LongMethodDetector Design Document

## 1. Purpose
`LongMethodDetector` は、構造解析で明示された `long_method` factを報告します。
行数や固定閾値から長大性を推測しません。

## 2. Structured Specification

### Input
- **Python**: `@refactoring_fact("long_method")` を持つ関数AST。
- **C#**: Roslynの `refactoringFacts`。

### Core Logic
1. PythonはASTの関数デコレータから明示factを取得します。
2. C#はRoslynが属性から出力した`refactoringFacts`を使用します。
3. Python以外のソース文字列は解析せず、構造解析要求を診断します。
4. 行数、コメント数、波括弧、正規表現、閾値は判定に使用しません。

### Test Cases
- **Happy Path**: 明示factを持つPython/C#メソッドが検出されること。
- **Edge Case**: factのないメソッドは行数に関係なく推測されないこと。
