# LogAnalyzer Design Document

## 1. Purpose
`LogAnalyzer` は、蓄積された対話ログや実行ログを定期的に分析（Batch Path）するためのモジュールです。複数のイベントをトランザクション単位で集約し、成功・失敗・改善のパターンを抽出することで、システムの振る舞いに対する深い洞察を提供します。

## 2. Structured Specification

### 2.1. ログ収集と集約 (`collect_logs`)
- **Input**: `days_back` (int) - 遡って分析する日数
- **Logic**:
  1. `days_back` が非負整数であることを検証します。
  2. `logs/` 配下の JSON Linesログをファイル単位・行単位で読み込みます。
  3. 不正JSON、非objectイベント、I/O失敗を `collection_diagnostics` に記録し、他の正常なファイルと行の処理は継続します。
  4. `session_id` に基づいて、一連のイベント（パイプライン開始からアクション実行、エラー発生まで）を一つの「トランザクション」として集約します。
  5. 各トランザクションには、ユーザー入力テキスト、意図解析結果、アクションの成否、発生したエラーリストが含まれます。

### 2.2. パターン抽出 (`extract_patterns`)
集約されたトランザクションの `learning_evidence` のうち、
`approved: true` が明示された構造化根拠だけを学習候補へ変換します。
根拠がない場合は、入力文や信頼度からパターンを推測しません。
- **成功パターン (`_extract_success_patterns`)**: 
  - `type: intent_example` の `intent` と `pattern` を採用します。
- **エラーパターン (`_extract_error_patterns`)**:
  - `type: error` の明示的な `error_code` を採用します。
- **改善機会 (`_identify_improvement_opportunities`)**:
  - `type: improvement` の `issue` と `pattern` を採用します。
- **明確化復帰パターン (`_extract_clarification_fix_patterns`)**:
  - `type: intent_correction` の `source_text` と `corrected_intent` を採用します。

## 3. Dependencies
- `dataclasses`, `collections`, `json`, `pathlib`: 基本機能
