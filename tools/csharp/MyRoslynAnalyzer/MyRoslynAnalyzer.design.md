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
4. メトリクスを集計し、`manifest.json` と `details` を生成する。

### Test Cases
- **Happy Path**:
  - **Scenario**: `.sln` を解析。
  - **Expected Output**: `manifest.json` が生成される。
- **Edge Cases**:
  - **Scenario**: 入力パスが無効。
  - **Expected Output / Behavior**: エラーを出力して終了。

## 3. Dependencies
- **External**: `Microsoft.CodeAnalysis`, `Microsoft.Build.Locator`
