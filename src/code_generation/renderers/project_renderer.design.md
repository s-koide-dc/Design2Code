# project_renderer Design Document

## 1. Purpose

`project_renderer` はプロジェクト/テストの `.csproj`、`Program.cs`、`appsettings.json` を生成する。

## 2. Structured Specification

### Input
- **Description**: プロジェクト名、ターゲットフレームワーク、パッケージ参照、DI 登録文字列。
- **Type/Format**: `str`, `list`
- **Example**:
  ```json
  {
    "project_name": "OrdersProject",
    "target_framework": "net8.0"
  }
  ```

### Output
- **Description**: 各ファイルの C# / JSON / XML ソース。
- **Type/Format**: `str`
- **Example**: `"<Project Sdk=...>"`

### Core Logic
1. Web プロジェクト用の `.csproj` を生成し、`Tests` を除外する `ItemGroup` を含める。
2. テスト用 `.csproj` を生成し、xUnit 参照と本体プロジェクト参照を追加する。
3. `Program.cs` を生成し、サービス/リポジトリ/DB の DI 登録を挿入する。
4. `appsettings.json` の既定接続文字列を出力する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 既定値で `.csproj` と `Program.cs` を生成する。
  - **Expected Output**: 期待する XML/コードが生成される。
- **Edge Cases**:
  - **Scenario**: パッケージ参照が空。
  - **Expected Output / Behavior**: `ItemGroup` が空のまま出力される。

## 3. Dependencies
- **Internal**: なし
