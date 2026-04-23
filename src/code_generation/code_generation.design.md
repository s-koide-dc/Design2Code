# code_generation Design Document

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
- **Example**: `C:\workspace\NLP\OrdersProject\Program.cs` ほか

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

### Test Cases
- **Happy Path**:
  - **Scenario**: 最小の `entities` と `dtos` を持つ仕様で生成。
  - **Expected Output**: `Models/`, `DTO/`, `Program.cs`, `<Project>.csproj` が作成される。
- **Edge Cases**:
  - **Scenario**: `entity_specs` が空。
  - **Expected Output / Behavior**: `generation_hints` と `modules` から既定値を構築して生成する。
  - **Scenario**: `modules` に宣言されていない Controller/Service/Repository がある。
  - **Expected Output / Behavior**: 警告が標準出力に表示される。

## 3. Dependencies
- **Internal**:
  - `code_synthesis`
  - `test_generator`
  - `config_manager`
  - `logic_auditor`
  - `design_doc_refiner`
  - `vector_engine`
