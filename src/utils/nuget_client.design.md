# NuGetClient Design Document

## 1. Purpose (Updated 2026-02-10)
`NuGetClient` は、C# のビルドエラー（シンボル未解決）を解消するために、名前空間や型名から対応する NuGet パッケージを特定する責務を持ちます。NuGet Search API を利用した動的な解決と、解決結果の永続的な保持（学習）を提供します。

## 2. Structured Specification

### Input
- **Constructor**:
    - `config_manager`: 設定マネージャ（`dependency_map_path` を提供）。
- **Method `resolve_package`**:
    - `namespace_or_name`: 解決したい名前空間または型名（例: `YamlDotNet.Serialization`）。

### Output
- **Package Info**: `{"name": "PackageID", "version": "1.2.3"}` の形式。見つからない場合は `None`。

### Core Logic
1.  **初期化とロード**: 起動時に `resources/dependency_map.json` を読み込み、メモリ上のキャッシュ (`_cache`) を初期化します。
2.  **キャッシュ検索**: 要求されたシンボルがキャッシュに存在すれば即座に返却します。
3.  **NuGet API 検索**:
    - キャッシュにない場合、`https://azuresearch-usnc.nuget.org/query` にクエリを投げます。
    - 取得した結果の ID とクエリの類似度を検証し、関連性が高いと判断されたパッケージを採用します。
4.  **永続化 (`save`)**: メモリ上のキャッシュ情報を `dependency_map.json` に書き出します。

### Test Cases
- **Happy Path**:
  - **Input**: "YamlDotNet"
  - **Expected**: `{"name": "YamlDotNet", ...}`
- **Persistence Path**:
  - 解決成功後に `save()` を呼び出し、ファイルが生成されること。
  - 次回起動時にそのファイルからデータが復元されること。

## 3. Storage
- **File**: `resources/dependency_map.json`
- **Format**: `{ "SymbolName": { "name": "PackageID", "version": "x.y.z" }, ... }`