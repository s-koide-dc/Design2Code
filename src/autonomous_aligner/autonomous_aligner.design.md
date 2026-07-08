# autonomous_aligner Design Document

## 1. Purpose

`AutonomousAligner` は設計書と実装の整合性を監査し、修正候補を構造化して報告する。構造的な編集位置と変更後検証がない候補は適用しない。

## 2. Structured Specification

### Input
- **Description**: `*.design.md` と対応するソース。
- **Type/Format**: `Path`

### Output
- **Description**: 整合レポート。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. プロジェクト内の設計書を列挙し、対応するソースファイルを探索する。
2. `LogicAuditor` で設計書とコードの整合性を監査する。
3. 不整合がある場合は `CodeFixSuggestionEngine` で修正候補を生成し、`pending_suggestions` として返す。
4. スコア閾値や文字列一致を根拠にソースを書き換えない。
5. ビルドエラー修復も、構造的な編集位置と変更後検証が導入されるまでは適用しない。

### Test Cases
- **Happy Path**:
  - **Scenario**: 設計と実装が一致。
  - **Expected Output**: `status == "consistent"`。
- **Edge Cases**:
  - **Scenario**: ソースファイルが見つからない。
  - **Expected Output / Behavior**: `None` を返す。
  - **Scenario**: 不整合に対する修正候補が生成される。
  - **Expected Output / Behavior**: 元ファイルを変更せず、`status == "inconsistent"` と候補を返す。

## 3. Dependencies
- **Internal**: `logic_auditor`, `design_doc_parser`, `fix_engine`

## 4. Operational Notes
- `__main__` の整合レポート要約は `src.utils.stdout_guard.debug_print` による opt-in 出力とする。
- 通常のモジュール利用では stdout を使わず、監査・修復の進行は logger か呼び出し側の戻り値で扱う。
- 構造化ステップ契約が不足する監査結果は `indeterminate` とし、修正候補も生成しない。
