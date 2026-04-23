# CSharpOperations Design Document

## 1. Purpose (Updated 2026-02-10)
`CSharpOperations` は、独立したモジュールとして、C# ソースコードの静的解析（Roslynを使用）および `dotnet` コマンドを用いたテスト実行・結果解析を担当します。

## 2. Structured Specification

### 2.1. 初期化 (`__init__`)
- **Parameters**: `action_executor` - 親となる ActionExecutor インスタンス (移行期間中)
- **Logic**: ActionExecutor への参照を保持し、`_get_entity_value` や `_safe_join` などのヘルパーメソッドにアクセスできるようにします。

### 2.2. C# 静的解析 (`analyze_csharp`)
- **Input**: `filename` (対象ファイル名)
- **Core Logic**:
    1. 内部ツール `MyRoslynAnalyzer` を `dotnet run` で実行します。
    2. 解析結果（manifest.json および詳細 JSON）を一時ディレクトリに出力します。
    3. 解析結果を読み込み、クラス名、メソッド一覧、メトリクス（サイクロマティック複雑度等）を抽出します。
- **Output**: 抽出されたクラスとメトリクスのサマリー。`output_path` をコンテキストに保持し、後続のクエリで使用可能にします。

### 2.3. .NET テスト実行 (`run_dotnet_test`)
- **Input**: `project_path` (プロジェクトまたはソリューションのパス)
- **Core Logic**:
    1. **スマート・パス解決**: ターゲットが指定されない場合、`tests/generated/GeneratedTests.csproj` を優先的に探索し、自動的にテスト対象を決定します。
    2. **先行ビルド検証**: `dotnet test` 実行前に `dotnet clean` および `dotnet build` を実行します。ビルドに失敗した場合は、エラーログから主要な3件のエラーメッセージを抽出し、テスト実行をスキップして即時エラーを返します。
    3. **結果解析 (`parse_dotnet_test_result`)**: 
       - `dotnet test` の出力をパースし、失敗したテストメソッド名、期待値と実際値の乖離（Assertionメッセージ）を抽出します。
       - 合計、成功、失敗のカウントを構造化データとして返します。
- **Output**: テスト実行結果のサマリー。

### 2.4. 解析結果クエリ (`query_csharp_analysis_results`)
- **Input**: 
    - `output_path`: 解析結果が格納されているパス
    - `query_type`: クエリの種類 (class_summary, method_calls, impact_scope_method 等)
    - `target_name`: 対象のクラス名またはメソッド名
- **Core Logic**:
    1. 以前の解析結果（manifest/details）をメモリに再ロードします。
    2. **影響範囲特定 (`impact_scope`)**: `recursively_find_callers` を用いて、指定されたメソッドを直接・間接的に呼び出しているすべてのメソッドをコールグラフから再帰的に特定します。
    3. **メトリクス取得 (`method_metrics`)**: サイクロマティック複雑度、行数、およびコードのハッシュ値（同一性判定用）を取得します。
- **Output**: クエリに応じた詳細情報。

## 3. Dependencies
- **Internal**: `ActionExecutor` (移行用依存), `MyRoslynAnalyzer` (ツール)
- **External**: `os`, `json`, `subprocess`, `re`, `time`

## 4. Error Handling
- ビルドエラー時の詳細メッセージ出力
- 解析ツール失敗時のエラーログ取得
- パス不備のチェック
