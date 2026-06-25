# dynamic_harvester Design Document

## 1. Purpose
`dynamic_harvester`モジュールは、C#の標準ライブラリや指定されたアセンブリから、リフレクションを使用してメソッド定義を動的に収穫（harvest）する責任を負います。これにより、テスト生成やコード合成時に、利用可能なメソッドの情報をオンデマンドで取得できます。

## 2. Structured Specification

### Input
- **Description**: 収穫対象の完全修飾型名。自然言語クエリから型を推測する経路は使用しません。
- **Type/Format**: `str`
- **Example**:
  ```python
  type_name = "System.IO.File"
  ```

### Output
- **Description**: 収穫されたメソッド情報のリスト。各メソッドは `MethodStore` 形式に変換されます。
- **Type/Format**: `List[Dict[str, Any]]`
- **Example**:
  ```json
  [
    {
      "id": "harvested_System.IO.File_ReadAllText",
      "name": "ReadAllText",
      "class": "System.IO.File",
      "return_type": "string",
      "params": [
        {"name": "path", "type": "string"}
      ],
      "code": "System.IO.File.ReadAllText({path})",
      "definition": "public static string ReadAllText(string path) { /* Compiled Library */ }",
      "namespace": "System.IO",
      "code_body": "public static string ReadAllText(string path) { /* Compiled Library */ }",
      "usings": ["System.IO"],
      "dependencies": [],
      "tags": ["harvested", "standard-lib"],
      "has_side_effects": false
    }
  ]
  ```

### Core Logic

#### 2.1. 初期化 (`__init__`)
1. ロガーを初期化します。
2. `config_manager` を保存します。
3. `method_capability_map.json` を読み込み、`MethodStorePolicy` を初期化します。

#### 2.2. 標準ライブラリ検索 (`search_standard_library`)
1. 入力を完全修飾型名として検証します。
2. サポート対象の名前空間でない場合は空リストを返します。
3. 有効な型名に対して `harvest_from_type` を呼び出します。
4. 収穫されたメソッドのリストを返します。

#### 2.3. 型からの収穫 (`harvest_from_type`)
1. 指定された型名に対するC# Inspectorコードを生成します（`_generate_inspector_code`）。
2. 一時ディレクトリを作成します。
3. 一時ディレクトリ内に `.csproj` ファイルと `Program.cs` ファイルを作成します。
4. `dotnet run` コマンドを実行して、Inspectorコードを実行します。
5. 標準出力からJSON形式のメソッド情報を抽出します。
6. JSON をパースして、`_convert_to_store_format` でMethodStore形式に変換します。
7. 一時ディレクトリをクリーンアップします。
8. 変換されたメソッドリストを返します。

#### 2.4. MethodStore形式への変換 (`_convert_to_store_format`)
1. リフレクション結果の各メソッドに対して、以下の情報を抽出します：
   - メソッド名
   - パラメータ（名前と型）
   - 戻り値の型
2. MethodStore形式の辞書を作成します：
   - `id`: 一意の識別子（例: `harvested_{type_name}_{method_name}`）
   - `name`: メソッド名
   - `class`: 型名
   - `return_type`: 戻り値の型
   - `params`: パラメータのリスト
   - `code`: 呼び出しコードのテンプレート
   - `definition`: メソッドのシグネチャ（ダミー）
   - `namespace`: 名前空間
   - `code_body`: メソッドの定義（ダミー）
   - `usings`: 必要な using ディレクティブ
   - `dependencies`: 依存関係（空リスト）
   - `tags`: タグ（["harvested", "standard-lib"]）
   - `has_side_effects`: 副作用の有無（デフォルトは false）
3. `MethodStorePolicy` で role / capabilities / param roles を正規化し、低価値 API を除外します。
4. `last_policy_audit` に accepted / pruned / prune_reasons を保存します。
5. 変換されたメソッドのリストを返します。

#### 2.5. Inspectorコード生成 (`_generate_inspector_code`)
1. 指定された型名に対するC#コードを生成します。
2. コードは以下の処理を実行します：
   - `Type.GetType` を使用して型を取得します。
   - 複数のアセンブリから型を検索します（System.Private.CoreLib, System.Runtime等）。
   - 型の public static メソッドを取得します（特殊メソッドを除外）。
   - 各メソッドの名前、戻り値の型、パラメータ情報を抽出します。
   - JSON形式でシリアライズして標準出力に出力します。
3. 生成されたC#コードを文字列として返します。

### Test Cases

#### Happy Path
- **Scenario**: 完全修飾型名でメソッドを収穫する
- **Input**: `type_name = "System.IO.File"`
- **Expected Output**: `System.IO.File` の public static メソッドのリストが返される

#### Edge Cases
- **Scenario**: 存在しない型名を指定する
- **Input**: `type_name = "NonExistent.Type"`
- **Expected Output**: 空のリストが返される

- **Scenario**: 完全修飾型名ではない入力を指定する
- **Input**: `query = "read file"`
- **Expected Output**: 空のリストが返される

- **Scenario**: dotnet run がタイムアウトする
- **Input**: 実行に30秒以上かかる型
- **Expected Output**: 空のリストが返され、警告がログに記録される

- **Scenario**: dotnet run がエラーを返す
- **Input**: コンパイルエラーを引き起こす型
- **Expected Output**: 空のリストが返され、警告がログに記録される

## 3. Dependencies
- **Internal**: `config_manager` (optional), `MethodStorePolicy`
- **External**: `os`, `json`, `subprocess`, `tempfile`, `logging`, `typing`
- **Tools**: `dotnet` CLI (C# コンパイラとランタイム)

## 4. Consumers
- **TestGenerator**: テスト生成時に利用可能なメソッドを検索するために使用します。
- **CodeSynthesizer**: コード合成時に標準ライブラリのメソッドを参照するために使用します。
- **AdvancedTDDSupport**: TDDサイクル中に必要なメソッドを動的に取得するために使用します。

## 5. Notes
- リフレクションを使用するため、メソッドの実装コードは取得できません。シグネチャのみが利用可能です。
- 一時ディレクトリとdotnet runを使用するため、実行には数秒かかる場合があります。
- 将来的には、キャッシュ機構を追加して、同じ型の再収穫を避けることが推奨されます。
- 自然言語クエリから型を推測する簡易キーワードマッチングは使用しません。呼び出し側は構造化された型名または収穫対象定義を渡します。
- pruning ルールは `resources/method_store_policy.json` で管理し、収穫後の除外理由は `last_policy_audit` で確認できます。

## 4. Review Notes
- 2026-03-31: Reviewed against current implementation; specification remains valid.
- 2026-06-25: `query_map` による自然言語キーワード推測を廃止し、完全修飾型名の明示指定と `MethodStorePolicy` による正規化・pruning に更新。
- 2026-06-25: pruning ルールを `resources/method_store_policy.json` 管理にし、`last_policy_audit` で除外理由を追跡する構成へ更新。

