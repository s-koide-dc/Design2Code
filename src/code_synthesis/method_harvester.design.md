# method_harvester 設計ドキュメント (Class: MethodHarvester)

## 1. 目的 (Purpose)
`MethodHarvester` は、プロジェクト内の既存のソースコードから再利用可能なメソッドを自動的に抽出・カタログ化し、`MethodStore` を動的に拡充することを目的とします。これにより、AIが合成するための「材料」を自給自足します。

## 2. 構造化仕様 (Structured Specification)

### 2.1. 収集基準 (Harvesting Criteria)
- **アクセシビリティ**: `Public` のみ。
- **複雑度**: サイクロマティック複雑度（CC）が 5 以下かつ 0 より大きい（空でない）、シンプルで純粋な関数を優先。
- **有用性**: 引数または戻り値が存在すること。

### 2.2. 主要機能 (Core Logic)
1.  **スキャン実行**: `MyRoslynAnalyzer` を実行し、全クラス・メソッドのメタデータを取得。
2.  **部品フィルタリング**: 上記の基準に基づき、汎用部品として適格なメソッドを選別。
3.  **自動タグ付け**: `SymbolMatcher` と `domain_dictionary.json` を使い、メソッド名や Docstring から「バリデーション」「データ取得」などのタグを自動生成。
4.  **副作用検知**: メソッドボディをスキャンし、`File`, `Directory`, `HttpClient`, `Database` などの I/O 操作が含まれる場合に `has_side_effects` フラグを付与。
5.  **依存関係の自律解決**: 静的マップにない `using` 句を発見した場合、`NuGetClient` を介して NuGet API でパッケージ ID を自動特定。
6.  **ストア同期**: 選別されたメソッドを `method_store.json` 形式に変換し、既存のストアとマージ。

### 2.3. 入力 (Input) / 出力 (Output)
- **Input**: `MyRoslynAnalyzer` の出力ディレクトリパス。
- **Output**: 
    - `has_side_effects`, `dependencies`, `usings` 等の付加情報を含むメソッドメタデータ。
    - 更新された `resources/method_store.json`。

## 3. 依存関係 (Dependencies)
- `src/action_executor/operations/csharp_ops.py` (解析実行)
- `src/utils/symbol_matcher.py` (タグ付け)
- `src/utils/nuget_client.py` (依存関係解決) 【NEW】
- `resources/domain_dictionary.json`

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.

