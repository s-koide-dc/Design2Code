# test_generator Design Document
<!-- metadata-sync: 2026-07-09T00:00:00+09:00 -->

## 1. Purpose (Updated 2026-07-08)

`test_generator` はソースコード解析結果や設計書の Test Cases からテストコードを生成する。  
C# と Python を対象に、テンプレートと解析結果を使ってテストファイルを作成する。

### 1.1 Implementation Sync Notes (2026-07-08)
- canonical knowledge の `test_generator` 設定読取に失敗した場合、例外を握りつぶさず `configuration_diagnostics` に `source` / `operation` / `error_type` を記録する。
- `design` モードは `configuration_diagnostics` を `generation_diagnostics` へ引き継ぎ、診断がある場合は `status == "warning"` とする。
- Python source mode ではメソッド引数情報がない場合、未完成テストを生成せず `test_generation_unresolved` / `python_method_signature_not_available` を返す。

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
6. designモードで `{` または `[` から始まる入力・期待値は明示JSONとして扱う。JSON解析に失敗した場合は `generation_diagnostics` にシナリオ、操作、例外型を記録し、`status == "warning"` を返す。
7. JSONではないレガシー入力のフォールバックは許容するが、破損した明示JSONを正常生成として扱わない。
8. コンストラクタAST解析に失敗した場合は想定例外型を診断へ記録し、裸の例外捕捉で黙殺しない。
9. 生成Pythonの既定コンストラクタ遅延は `TypeError` のみ捕捉し、生成時に破損値をコードへ直接埋め込まない。
10. Pythonメソッドの signature が解析結果に存在しない場合は、生成済みファイルを残さず error result を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: C# ソースからテスト生成。
  - **Expected Output**: `generated_files` に `.cs` テストが含まれる。
- **Edge Cases**:
  - **Scenario**: ソースファイルが存在しない。
  - **Expected Output / Behavior**: `status == "error"` を返す。
  - **Scenario**: Test Caseの明示JSONが破損している。
  - **Expected Output / Behavior**: `status == "warning"`、`generation_diagnostics` に `JSONDecodeError` を記録し、生成Pythonは構文上有効。
  - **Scenario**: Python source mode でメソッド signature が無い。
  - **Expected Output / Behavior**: `status == "error"`、`error.type == "test_generation_unresolved"`、生成ファイルを作らない。

## 3. Dependencies
- **Internal**: `ast_analyzer`, `dummy_factory`, `design_doc_parser`
- **External**: `os`, `json`, `ast`

## 4. Review Notes
- 2026-04-14: service_test_* 連携と生成モード分岐を現行実装に合わせて再確認。
- 2026-06-30: design test caseのJSON/AST診断、warning契約、生成Pythonの限定例外処理を反映。
- 2026-07-08: canonical knowledge 設定診断、design mode への診断伝播、Python signature 不明時の生成拒否契約を反映。
