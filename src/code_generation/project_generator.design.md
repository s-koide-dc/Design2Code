# project_generator Design Document

## 1. Purpose

`project_generator` は `ProjectSpecParser` の出力を元に、C# の多ファイルプロジェクト（API + DTO + Repository + Service + Tests）を生成する。

## 2. Structured Specification

### Input
- **Description**: プロジェクト仕様辞書と出力先ディレクトリ。
- **Type/Format**: `Dict[str, Any]` + `str`
- **Example**:
  ```json
  {
    "project_name": "OrdersProject",
    "spec": {
      "tech": { "Target": "net8.0" },
      "data_access": { "Provider": "SqlServer", "Strategy": "Dapper" },
      "modules": [],
      "entities": [],
      "dtos": [],
      "method_specs": {},
      "validation": {},
      "generation_hints": {}
    }
  }
  ```

### Output
- **Description**: 出力ディレクトリに C# プロジェクト一式を生成する。
- **Type/Format**: Filesystem
- **Example**: `C:\workspace\NLP\OrdersProject\Program.cs` ほか

### Core Logic
1. `spec` から `tech/data_access/modules/entities/dtos/method_specs/validation/generation_hints` を抽出する。
2. テンプレート `steps.json` と `validation.json` を読み込む。
3. `entity_specs` が空の場合は `generation_hints` と `modules` から既定値を構成する。
4. `method_specs` が不足している場合は、CRUD テンプレートとエンティティ定義に基づいて内部的に補完する。  
   - サービス: `steps` / `core_logic` / `test_cases` を標準 CRUD で生成する。  
   - リポジトリ: SQL を含む `core_logic` と `steps` を標準 CRUD で生成する。
5. DTO マッピングが未指定の場合は、同名プロパティのみを自動対応付けする。  
   - `CreateRequest` → `Entity`、`Entity` → `Response` の順で補完する。
6. `method_specs` に既存の CRUD 指定がある場合は、同一種別のデフォルト補完を行わない。  
   - 例: `InventoryService.GetInventoryItems` が `service.list` を持つなら `GetInventory` は補完しない。
7. Modules のメソッドシグネチャに `?` が含まれる場合は、サービス/リポジトリの戻り値型に反映する。  
8. 必要な出力ディレクトリを作成する。  
   - `[ACTION|PERSIST|void|void|FILE] [semantic_roles:{"path":"<output_root>/*"}]`
9. `entities` / `dtos` をレンダリングし、`Models/DTO` に書き出す。  
   - `[ACTION|PERSIST|string|void|FILE] [semantic_roles:{"path":"<output_root>/Models/<Entity>.cs"}]`
   - `[ACTION|PERSIST|string|void|FILE] [semantic_roles:{"path":"<output_root>/DTO/<Dto>.cs"}]`
10. `entity_specs` 単位で CRUD 名称/DTO/ID 型/バリデーションを解決し、サービス/リポジトリのメソッド本体を構築する。
   - `method_specs` の `steps` が `service.*` / `repo.*` を含む場合、そのメソッド名を CRUD テンプレートより優先する。
11. サービス/リポジトリのインターフェイスと実装をレンダリングし保存する。
12. ルート定義があれば、コントローラをレンダリングする。`USE_CODE_SYNTH_PROJECT_ALL` が有効なら合成器でアクション本体を生成する。
   - `routes` からベースパスを推定し、二重パス（例: `catalogitems/catalog`）にならないようにする。
13. `Program.cs` / `appsettings.json` / `<Project>.csproj` / テストプロジェクトを生成する。
14. `LogicAuditor` と `DesignDocRefiner` でロジック/設計書監査を行い、警告を出力する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 最小構成の `entities` / `dtos` を含む仕様。
  - **Expected Output**: `Models/DTO/Services/Repositories/Controllers/Program.cs` が生成される。
- **Edge Cases**:
  - **Scenario**: `entity_specs` が空。
  - **Expected Output / Behavior**: `generation_hints` と `modules` から既定値を構築する。
  - **Scenario**: `modules` に宣言されていない Controller/Service/Repository がある。
  - **Expected Output / Behavior**: 警告が標準出力に表示される。

## 3. Dependencies
- **Internal**:
  - `template_engine`
  - `design_ops_resolver`
  - `code_synthesis`
  - `test_generator`
  - `logic_auditor`
  - `design_doc_refiner`
  - `config_manager`
  - `vector_engine`
