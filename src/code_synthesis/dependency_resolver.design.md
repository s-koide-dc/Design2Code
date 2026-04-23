# DependencyResolver Design Document

## 1. Purpose
`DependencyResolver` は、C# ソースコード内の未解決の型や名前空間から、導入すべき適切な NuGet パッケージを特定する責任を負います。`NuGetClient` の単純な検索に加え、既知のマッピング（`dependency_map.json`）の管理と、プロジェクト固有の解決戦略をカプセル化します。

## 2. Structured Specification

### Input
- **Method `resolve`**:
    - `symbol`: 解決したい型名または名前空間。
- **Method `analyze_errors`**:
    - `build_errors`: `CompilationVerifier` から返されたエラーリスト。

### Output
- **PackageInfo**: パッケージ名と推奨バージョンの辞書。

### Core Logic
1.  **既知のマッピング確認**: `resources/dependency_map.json` を優先的に参照。
2.  **NuGet 検索**: マッピングがない場合、`NuGetClient` を用いて検索。
3.  **エラー解析統合**: ビルドエラー (CS0246) からシンボルを自動抽出し、解決を試みる。

## 3. Dependencies
- **Internal**: `nuget_client`
- **External**: `json`, `os`

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.

