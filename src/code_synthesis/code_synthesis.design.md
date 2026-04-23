# Code Synthesis Design Document

## 1. Purpose (Updated 2026-04-14)

`code_synthesis` は `StructuredSpec` からコードを合成し、必要であれば検証・再計画を行う。  
中心となる入口は `synthesis_pipeline.synthesize_structured_spec` であり、合成・検証・再計画・依存解決を統合する。

## 2. Structured Specification

### Input
- **Description**: 構造化仕様、合成器、メソッド名、および検証/再計画器。
- **Type/Format**: `Dict[str, Any]` + `CodeSynthesizer` + `str`
- **Example**:
  ```json
  {
    "structured_spec": { "steps": [] },
    "method_name": "CreateOrder"
  }
  ```

### Output
- **Description**: 合成結果。コード、トレース、検証結果、依存解決結果を含む。
- **Type/Format**: `Dict[str, Any]`
- **Example**:
  ```json
  {
    "status": "OK",
    "code": "public ...",
    "verification": { "valid": true, "errors": [] }
  }
  ```

### Core Logic
1. `validate_structured_spec_or_raise` で `StructuredSpec` を検証する。
2. `synthesizer.synthesize_from_structured_spec` を呼び出し、初期コードとトレースを生成する。
3. `spec_auditor` があれば `spec_issues` を収集する。
4. 依存解決用の `usings` から `resolve_nuget_deps` を呼び、NuGet 依存関係を確定する。
5. `verifier` があれば生成コードを検証し、`verification` を記録する。
6. `allow_retry` と `replanner` が有効なら最大 `max_retries` 回の再計画を実行する。
   - `// TODO` の残存、検証失敗、`spec_auditor` の問題、`replanner` による不一致検出がある場合に再計画を実施。
   - `SPEC_INPUT_LINK_UNUSED` はブロッキングとして扱う。
   - `replanner.replan` により IR をパッチし、`_synthesize_from_ir_tree` で再合成する。
   - 再合成後に `spec_auditor` と `verifier` を再実行する。
7. 最終結果に `spec_issues` / `verification` / `resolved_dependencies` を付与して返却する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 合成が成功し、検証もパスする。
  - **Expected Output**: `status == "OK"` かつ `verification.valid == true`。
- **Edge Cases**:
  - **Scenario**: 合成が失敗する。
  - **Expected Output / Behavior**: `status == "FAILED"` を返す。
  - **Scenario**: `allow_retry` 有効で `// TODO` が残る。
  - **Expected Output / Behavior**: `replanner.replan` が呼ばれ再合成される。

## 3. Dependencies
- **Internal**: `design_parser`, `code_synthesizer`, `synthesis_pipeline`, `action_utils`

## 4. Review Notes
- 2026-03-31: action_handlers の import 更新に合わせて仕様整合を再確認。
- 2026-04-14: 合成→検証→再計画の流れとブロッキング条件（SPEC_INPUT_LINK_UNUSED）を現行実装に合わせて再確認。
- 2026-04-21: method_store のベクトルDB保存先統一（`config.storage_dir`）と旧配置移行方針を反映。
