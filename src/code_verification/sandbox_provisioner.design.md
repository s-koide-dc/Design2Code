# sandbox_provisioner Design Document

## 1. Purpose

`sandbox_provisioner` は検証用の隔離 C# プロジェクトを一時生成し、NuGet 復元を行う。

## 2. Structured Specification

### Input
- **Description**: プロジェクト名と依存パッケージ一覧。
- **Type/Format**: `str`, `List[Dict[str, str]]`
- **Example**: `project_name="Sandbox", dependencies=[{"name":"Dapper","version":"2.1.35"}]`

### Output
- **Description**: 作成されたサンドボックスディレクトリのパス。
- **Type/Format**: `Path`
- **Example**: `C:\\Users\\...\\Temp\\gemini_nlp_sandbox`

### Core Logic
1. 既存の一時ディレクトリがあれば削除する。
2. 依存パッケージを含む最小 `csproj` を生成する。
3. `dotnet restore` を実行して依存を復元する。
4. ディレクトリパスを返す。失敗時は警告を出す。
5. `clean_up` で一時ディレクトリを削除する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 有効な依存を持つ。
  - **Expected Output**: サンドボックスが作成されパスが返る。
- **Edge Cases**:
  - **Scenario**: `dotnet restore` 失敗。
  - **Expected Output / Behavior**: 警告が出るがパスは返る。

## 3. Dependencies
- **Internal**: `config_manager`
