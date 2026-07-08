# MyRoslynAnalyzer Design Document

## 1. Purpose

`MyRoslynAnalyzer` は C# ソリューション/プロジェクトを解析し、  
クラス・メソッド・依存関係・メトリクスを JSON で出力する。

## 2. Structured Specification

### Input
- **Description**: 解析対象パスと出力先。
- **Type/Format**: `MyRoslynAnalyzer.exe <input_path> <output_path> [--exclude <pattern>]`

### Output
- **Description**: `manifest.json` と `details/<id>.json`。
- **Type/Format**: JSON files

### Core Logic
1. `MSBuildWorkspace` で solution/project をロードする。
2. 定義ウォーカーで型・メソッド・プロパティを抽出する。
3. 依存関係ウォーカーで呼び出し/参照を解析する。
4. 条件構文から、論理AND/ORの混在とBooleanグループ否定を
   `conditionStructures[].facts`として出力する。
5. 型とメソッドの`RefactoringFactAttribute`文字列引数を`refactoringFacts`として出力する。
6. メソッドの`DuplicateGroupAttribute`文字列引数を`duplicateGroupId`として出力する。
7. メトリクスを集計し、`manifest.json` と `details` を生成する。
8. 除外パターンは `FileSystemName.MatchesSimpleExpression` で評価し、独自の正規表現変換を行わない。

### Test Cases
- **Happy Path**:
  - **Scenario**: `.sln` を解析。
  - **Expected Output**: `manifest.json` が生成される。
- **Edge Cases**:
  - **Scenario**: 入力パスが無効。
  - **Expected Output / Behavior**: エラーを出力して終了。
  - **Scenario**: `a && b || c` を含むメソッドを解析。
  - **Expected Output / Behavior**: `mixed_boolean_operators` factが出力される。

## 3. Dependencies
- **External**: `Microsoft.CodeAnalysis`, `Microsoft.Build.Locator`

## 4. Review Notes

- 2026-06-30: visitor内の重複nullチェックを除去し、wildcard評価を標準APIへ移行。
- 2026-07-06: 条件式の固定複雑度スコア判定を避けるため、Roslyn構文factを追加。
- 2026-07-07: クラス/構造体の明示的なリファクタリングfact出力を追加。
- 2026-07-07: メソッドの明示的な重複グループID出力を追加。
