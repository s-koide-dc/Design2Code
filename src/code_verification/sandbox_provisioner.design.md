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
- **Example**: `C:\\Users\\...\\Temp\\nlp_codegen_sandbox_<unique-id>`

### Core Logic
1. 実行ごとに所有する一意な一時ディレクトリを生成する。呼び出し元のプロジェクト名はパスへ使わず、内部固定名 `Sandbox.csproj` を使う。
2. `dependency_contract` で検証・XMLエスケープ済みの依存パッケージだけを含む最小 `net10.0` の `csproj` を生成する。
3. `dotnet restore` を実行して依存を復元する。
4. ディレクトリパスを返す。失敗時は警告を出す。
5. `clean_up` は当該インスタンスが生成した一時ディレクトリだけを削除する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 有効な依存を持つ。
  - **Expected Output**: サンドボックスが作成されパスが返る。
- **Edge Cases**:
  - **Scenario**: `dotnet restore` 失敗。
  - **Expected Output / Behavior**: 警告が出るがパスは返る。

## 3. Dependencies
- **Internal**: `dependency_contract`

## 4. Operational Notes
- `dotnet restore` 失敗の補助診断は stdout ではなく logger の warning に記録する。
- サンドボックス生成 API 自体は返り値の `Path` を正式結果とし、常時標準出力は持たない。
