# autonomous_aligner Design Document

## 1. Purpose

`AutonomousAligner` は設計書と実装の整合性を監査し、必要に応じて修正案を適用する。

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
3. 不整合がある場合は `CodeFixSuggestionEngine` で修正案を生成する。
4. 安全スコアが高い修正案を適用し、最大 5 回まで再監査する。
5. ビルドエラーがある場合はエラー情報に基づく自動修復を試行する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 設計と実装が一致。
  - **Expected Output**: `status == "consistent"`。
- **Edge Cases**:
  - **Scenario**: ソースファイルが見つからない。
  - **Expected Output / Behavior**: `None` を返す。

## 3. Dependencies
- **Internal**: `logic_auditor`, `design_doc_parser`, `fix_engine`
