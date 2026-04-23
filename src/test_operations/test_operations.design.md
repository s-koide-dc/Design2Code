# TestAndCoverageOperations Design Document

## 1. Purpose (Updated 2026-04-14)

`TestAndCoverageOperations` はテスト生成とカバレッジ計測を実行する。  
`ActionExecutor` から呼び出され、`test_generator` と `coverage_analyzer` を利用する。

## 2. Structured Specification

### Input
- **Description**: `filename` / `project_path` / `language` / `output_path`。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: `action_result` を更新したコンテキスト。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. `generate_test_cases` は対象ファイルを解決し、`TestGenerator.generate_tests` を実行する。
2. クラス名入力の場合は解析結果 `manifest.json` を参照してソースパスを解決する。
3. `measure_coverage` / `analyze_coverage_gaps` / `generate_coverage_report` は `CoverageAnalyzer.analyze_project` を呼び出す。
4. 成功時はサマリーと生成物パスを `action_result` に格納する。

### Test Cases
- **Happy Path**:
  - **Scenario**: C# ソースからテスト生成。
  - **Expected Output**: `generated_files` が返る。
- **Edge Cases**:
  - **Scenario**: `project_path` が存在しない。
  - **Expected Output / Behavior**: `status == "error"`。

## 3. Dependencies
- **Internal**: `test_generator`, `coverage_analyzer`, `csharp_operations`
- **External**: `os`

## 4. Review Notes
- 2026-04-14: 解析結果からのソース解決とカバレッジ連携の記述を現行実装に合わせて再確認。
