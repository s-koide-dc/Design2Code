# Code Synthesis Design Document

## 1. Purpose (Updated 2026-06-18)

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
8. runtime bridge では `ActionSynthesizer` と `IREmitter` が役割分担する。
   - 弱い `spec_role=TRANSFORM` は `ActionSynthesizer` が `src.utils.semantic_intents` の `INTENT_TRANSFORM` へ補正して specialized handler に渡す。
   - `spec_role=ITERATE` は `ActionSynthesizer` が `NODE_LOOP` を主に消費しつつ、exact upstream collection と deterministic item entity を metadata から優先する。
   - `spec_role=WRAP` は `IREmitter` が structural consumer として child body を保持し、`wrapper_kind` に応じて `retry`, explicit `timeout`, explicit `transaction` statement へ再構成する。
   - `spec_role=CALCULATE` は `ActionSynthesizer` / `calc_ops` が `entity_resolution`, `calculate_target_resolution`, `calculate_source_resolution` を読み、exact source と target/property の強さに応じて concretization を制御する。
9. review/audit 系 CLI では、同じ合成入口を使って `.design.md -> .inferred.design.md -> generated .cs -> spec audit -> compile verification` を一気通しで確認する。
10. resilient IO/NETWORK/DB 合成では、scalar 戻り値 (`string`, `bool`, `int` など) も explicit `var_type` を保持し、退避変数の hoist 時に `var x = null` のような不正宣言を出さない。
11. 現在の最小 authoring 境界で重点確認している生成経路は file / db / http / env の代表シナリオであり、各系統は review snapshot で `SpecAuditor` と compile verification まで通すことを前提にする。

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
- 2026-05-11: `TRANSFORM` の weak-intent bridge と `WRAP` の retry-statement structural consumer を module-level specification に反映。
- 2026-05-13: explicit `WRAP/timeout` の structural consumer を追加し、sync/async timeout guard へ決定論的に落とす方針を反映。
- 2026-05-13: explicit `WRAP/transaction` の structural consumer を追加し、sync/async `TransactionScope` へ決定論的に落とす方針を反映。
- 2026-05-13: `ITERATE` の collection/item provenance bridge（exact upstream collection と deterministic item entity 優先）を module-level specification に反映。
- 2026-05-13: `CALCULATE` の source/target provenance（`default_scope_var`, `calculate_target_resolution`）に応じて over-concretization を避ける方針を反映。
- 2026-06-18: review snapshot による実コード監査経路、resilient scalar return hoisting、file/db/http/env の最小シナリオ検証前提を反映。
