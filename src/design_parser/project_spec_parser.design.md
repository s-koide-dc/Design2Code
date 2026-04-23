# project_spec_parser Design Document

## 1. Purpose

`project_spec_parser` はプロジェクト仕様書（Markdown）を解析し、プロジェクト生成に必要な構造化辞書へ変換する。

## 2. Structured Specification

### Input
- **Description**: プロジェクト仕様の Markdown 文字列、またはファイルパス。
- **Type/Format**: `str` (Markdown / File Path)
- **Example**: `"# OrdersProject\n## Project Spec\n### Tech\n- **Target**: net8.0"`

### Output
- **Description**: プロジェクト名と仕様辞書、セクション分割結果を含む構造化データ。
- **Type/Format**: `Dict[str, Any]`
- **Example**:
  ```json
  {
    "project_name": "OrdersProject",
    "spec": {
      "tech": { "Target": "net8.0" },
      "architecture": {},
      "data_access": {},
      "modules": [],
      "entities": [],
      "dtos": [],
      "infrastructure": {},
      "validation": {},
      "method_specs": {},
      "generation_hints": {}
    },
    "raw_sections": {}
  }
  ```

### Core Logic
1. 入力がファイルパスの場合は読み込み、Markdown 文字列として扱う。
2. `#` ヘッダ単位でセクション分割し、`raw_sections` として保持する。
3. `#` で始まる最初のヘッダから `project_name` を抽出する。なければ既定値を返す。
4. `Project Spec` セクションがある場合は、その配下の `###` サブセクションを解析する。なければトップレベルを代用する。
5. `Tech / Architecture / Data Access / Infrastructure` は `- **Key**: Value` 形式の KV ブロックとして辞書化する。
6. `Modules` は `- **Role**: Name` と、任意のサブリスト（`- dependencies:` など）を配列に変換する。
7. `Entities / DTO` は `- **Entity**:` / `- **DTO**:` ブロックと `- prop` 行を解析し、`entities` / `dtos` を生成する。
8. `Validation` は KV ブロックとして読み取り、値を `,` 区切り配列に分解する。
9. `Method Specs` は `###` 見出し配下の `Input/Output/Core Logic/Test Cases` を抽出して辞書化する。
   - `Test Cases` が JSON 形式（`{...}`）の場合は構造化オブジェクトとして読み取る。
10. `Generation Hints` は `Entities/SQL Template/Validation Template/DTO Mapping/CRUD Method Template/Entity Specs` を解析し、`generation_hints` に格納する。

### Test Cases
- **Happy Path**:
  - **Scenario**: `Project Spec` と `Method Specs` を含む設計書を解析する。
  - **Expected Output**: `project_name` と `spec` が正しく埋まり、`method_specs` が取得できる。
- **Edge Cases**:
  - **Scenario**: `Project Spec` が無い。
  - **Expected Output / Behavior**: トップレベルセクションを代用して解析する。
  - **Scenario**: 見出しが無い。
  - **Expected Output / Behavior**: `project_name` が `"UnknownProject"` となる。

## 3. Dependencies
- **Internal**: なし
