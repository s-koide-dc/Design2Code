# synthesis_pipeline Design Document

## 1. Purpose

`synthesis_pipeline` は構造化設計仕様からコード合成を行い、依存解決・検証・再試行を含めた合成結果を返す。

## 2. Structured Specification

### Input
- **Description**: 合成器と構造化仕様、メソッド名、および任意の検証/再計画コンポーネント。
- **Type/Format**:
  - `synthesizer`: CodeSynthesizer 互換オブジェクト
  - `structured_spec`: `Dict[str, Any]`
  - `method_name`: `str`
  - optional: `verifier`, `replanner`, `spec_auditor`, `nuget_client`
  - flags: `return_trace`, `allow_retry`, `allow_fallback`, `max_retries`
- **Example**:
  ```json
  {
    "method_name": "GetOrders",
    "structured_spec": { "steps": [] },
    "allow_retry": true
  }
  ```

### Output
- **Description**: 合成結果（ステータス、コード、検証結果、依存パッケージなど）。
- **Type/Format**: `Dict[str, Any]`
- **Example**:
  ```json
  {
    "status": "SUCCESS",
    "code": "public class ...",
    "trace": {},
    "verification": { "valid": true, "errors": [] },
    "resolved_dependencies": [],
    "spec_issues": []
  }
  ```

### Core Logic
1. `validate_structured_spec_or_raise` で `structured_spec` を検証する。
2. `synthesizer.synthesize_from_structured_spec` を呼び出し、失敗時は即時返却する。
3. `dependencies` を抽出し、`nuget_client` があれば NuGet 依存を解決する。
4. `verifier` があればコード検証を実行し、結果を保持する。
5. `spec_auditor` があれば仕様監査を実行し、`spec_issues` を収集する。
6. `allow_retry` が無効、または `replanner` が無い場合は現在の結果に検証情報を添えて返す。
7. 再試行が有効な場合、`TODO` 残存・検証失敗・ロジック不一致・仕様不整合を判定する。
8. `replanner.replan` で IR を補正し、`_synthesize_from_ir_tree` で再合成する。
9. 再合成後に依存解決・検証・監査をやり直し、最大回数まで繰り返す。
10. 最終結果に `spec_issues / verification / resolved_dependencies` を付与して返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 検証が成功し再試行不要。
  - **Expected Output**: `status=SUCCESS` と検証結果が付与される。
- **Edge Cases**:
  - **Scenario**: 初回合成が失敗。
  - **Expected Output / Behavior**: `FAILED` 結果をそのまま返す。
  - **Scenario**: `allow_retry=true` かつ `replanner` が再計画失敗。
  - **Expected Output / Behavior**: 再試行を打ち切り直近の結果を返す。

## 3. Dependencies
- **Internal**: `design_parser`
