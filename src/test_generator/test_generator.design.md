# test_generator Design Document

## 1. Purpose (Updated 2026-04-14)

`test_generator` はソースコード解析結果や設計書の Test Cases からテストコードを生成する。  
C# と Python を対象に、テンプレートと解析結果を使ってテストファイルを作成する。

## 2. Structured Specification

### Input
- **Description**: モード、ソースファイル、解析出力、設計書パス。
- **Type/Format**: `str`, `Dict[str, Any]`

### Output
- **Description**: 生成ファイルパスとテストケース情報。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. `generate_tests` で `source` / `design` / `service` のモードを分岐する。
2. `source` モードは AST または Roslyn 解析結果からクラス/メソッドを抽出し、テンプレートでテストコードを組み立てる。
3. `design` モードは `.design.md` の Test Cases を読み取り、設計書由来のシナリオでテストを生成する。
4. `service` モードは `service_test_builder` / `service_test_generator` を用い、CRUD 形式のサービス向けテストを生成する。
5. 出力先は `tests/generated` を既定とし、生成ファイル一覧を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: C# ソースからテスト生成。
  - **Expected Output**: `generated_files` に `.cs` テストが含まれる。
- **Edge Cases**:
  - **Scenario**: ソースファイルが存在しない。
  - **Expected Output / Behavior**: `status == "error"` を返す。

## 3. Dependencies
- **Internal**: `ast_analyzer`, `dummy_factory`, `design_doc_parser`
- **External**: `os`, `json`, `ast`

## 4. Review Notes
- 2026-04-14: service_test_* 連携と生成モード分岐を現行実装に合わせて再確認。
