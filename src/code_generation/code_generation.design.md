# code_generation Design Document
<!-- metadata-sync: 2026-07-16T00:00:00+09:00 -->

## 1. Purpose (Updated 2026-04-14)

`code_generation` はプロジェクト仕様（Project Spec）から C# の多ファイル構成を生成する。  
テンプレート（`templates/project`）とレンダラ群を利用し、モデル/DTO/サービス/リポジトリ/コントローラ/テスト/設定ファイルを出力する。  
`ProjectGenerator` は spec 完成・命名・controller/service/repo 生成・監査を各ヘルパーへ委譲する。

## 2. Structured Specification

### Input
- **Description**: `ProjectSpecParser` が生成したプロジェクト仕様と出力先ディレクトリ。
- **Type/Format**: `Dict[str, Any]` + `str`
- **Example**:
  ```json
  {
    "project_name": "OrdersProject",
    "spec": {
      "entities": [{"name":"Order","properties":["Id:int","Total:decimal"]}],
      "dtos": [{"name":"OrderCreateRequest","properties":["Total:decimal"]}]
    }
  }
  ```

### Output
- **Description**: 出力先に C# プロジェクト一式が生成される。
- **Type/Format**: Filesystem
- **Example**: `<workspace-root>/OrdersProject/Program.cs` ほか

### Core Logic
1. `ProjectGenerator.generate(spec, output_root)` で `project_name` / `tech` / `entities` / `dtos` / `method_specs` / `generation_hints` を抽出し、`spec_completion` と `spec_helpers` で不足情報を補完する。
2. `entity_specs` が空の場合、`generation_hints` と `modules` から既定のコントローラ/サービス/リポジトリ名を生成する。
3. 出力ディレクトリ（`Controllers/Services/Repositories/Models/DTO`）を作成する。  
   - `[ACTION|PERSIST|void|void|FILE] [semantic_roles:{"path":"<output_root>/*"}]` 出力ディレクトリを作成する。
4. `entities` / `dtos` をレンダリングし、対応する `.cs` を書き込む。  
   - `[ACTION|PERSIST|string|void|FILE] [semantic_roles:{"path":"<output_root>/Models/<Entity>.cs"}]` モデルを出力する。  
   - `[ACTION|PERSIST|string|void|FILE] [semantic_roles:{"path":"<output_root>/DTO/<Dto>.cs"}]` DTO を出力する。
5. 各 `entity_spec` について CRUD 名称/型/ルートを決定し、`repo_generation` / `service_generation` / `controller_generation` を用いてサービス/リポジトリ/コントローラを生成する。  
   - コントローラは `USE_CODE_SYNTH_PROJECT_ALL` が有効な場合に `CodeSynthesizer` を用いてアクション本体を合成する。
6. `Program.cs` / `appsettings.json` / `<Project>.csproj` / テストプロジェクトを生成する。  
   - `[ACTION|PERSIST|string|void|FILE] [semantic_roles:{"path":"<output_root>/Program.cs"}]`  
   - `[ACTION|PERSIST|string|void|FILE] [semantic_roles:{"path":"<output_root>/appsettings.json"}]`
7. `LogicAuditor` と `DesignDocRefiner` を用いて生成物の監査を行い、問題があれば警告を出力する。
8. `ProjectContractValidator` により、生成前のProjectSpec契約と生成後のController/Service/Repository/DIリンクを検証する。
9. `Tests/ProjectWiringTests.cs` を生成し、`WebApplicationFactory` でアプリケーションを起動して、宣言されたService/Repositoryが実DIコンテナから解決できることを確認する。
10. `Tests/ProjectEndpointTests.cs` を生成し、Repositoryをテスト代替に差し替えた上で、一覧GETとPOST/PUT/DELETEを `HttpClient` から実行し、Controller → Service → Repository の経路と成功レスポンスを確認する。
11. `Tests/ProjectSqliteEndpointTests.cs` を生成し、インメモリSQLiteへスキーマと初期データを作成して、生成RepositoryのSQL、Dapperマッピング、CRUD後のDB状態を検証する。
12. CRUD補完で仕様が省略された場合でも、取得・更新系のnullable戻り値を既定で反映し、生成コードのnullable警告を抑制する。明示的なモジュール署名・method specがある場合はそちらを優先する。
13. `ProjectEndpointTests.cs` では、対象なしのGET/PUT/DELETEと、検証規則がある場合の不正POSTについて、404/400のHTTPステータスを確認する。
14. `Tests/ProjectSqlServerEndpointTests.cs` を生成し、利用可能なLocalDB上に一時データベースを作成して、SQL Server実接続でCRUD経路とDB状態を確認する。テスト終了時にデータベースを削除する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 最小の `entities` と `dtos` を持つ仕様で生成。
  - **Expected Output**: `Models/`, `DTO/`, `Program.cs`, `<Project>.csproj` が作成される。
- **Edge Cases**:
  - **Scenario**: `entity_specs` が空。
  - **Expected Output / Behavior**: `generation_hints` と `modules` から既定値を構築して生成する。
  - **Scenario**: `modules` に宣言されていない Controller/Service/Repository がある。
  - **Expected Output / Behavior**: 警告が標準出力に表示される。
  - **Scenario**: Controller、Service、Repository、またはDI登録の生成物が層間契約から外れる。
  - **Expected Output / Behavior**: 生成後契約検証が失敗し、プロジェクト生成を失敗として扱う。

## 3. Dependencies
- **Internal**:
  - `code_synthesis`
  - `test_generator`
  - `config_manager`
  - `logic_auditor`
  - `design_doc_refiner`
  - `vector_engine`
