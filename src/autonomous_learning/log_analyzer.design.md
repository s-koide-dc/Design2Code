# LogAnalyzer Design Document

## 1. Purpose
`LogAnalyzer` は、蓄積された対話ログや実行ログを定期的に分析（Batch Path）するためのモジュールです。複数のイベントをトランザクション単位で集約し、成功・失敗・改善のパターンを抽出することで、システムの振る舞いに対する深い洞察を提供します。

## 2. Structured Specification

### 2.1. ログ収集と集約 (`collect_logs`)
- **Input**: `days_back` (int) - 遡って分析する日数
- **Logic**:
  1. `logs/` 配下の JSON ログファイルを走査し、指定期間内に更新されたイベントを読み込みます。
  2. `session_id` に基づいて、一連のイベント（パイプライン開始からアクション実行、エラー発生まで）を一つの「トランザクション」として集約します。
  3. 各トランザクションには、ユーザー入力テキスト、意図解析結果、アクションの成否、発生したエラーリストが含まれます。

### 2.2. パターン抽出 (`extract_patterns`)
集約されたトランザクションから以下のパターンを特定します。
- **成功パターン (`_extract_success_patterns`)**: 
  - 信頼度 0.7 以上で意図検出に成功し、アクションも正常終了した対話。
  - 共通するテキストパターン（n-gram または単語集合）を抽出し、意図検出ルール候補とします。
- **エラーパターン (`_extract_error_patterns`)**:
  - 頻発する実行時エラーやアクション失敗をタイプ別に分類します。
- **改善機会 (`_identify_improvement_opportunities`)**:
  - 意図検出の信頼度が低いケースや、頻繁に「明確化」が発生している入力。
- **明確化復帰パターン (`_extract_clarification_fix_patterns`)**:
  - AIの聞き返し（明確化）に対して、ユーザーが同意したり訂正したりして最終的に成功したケースから、誤認されやすいパターンの補正情報を抽出します。

## 3. Dependencies
- `dataclasses`, `collections`, `json`, `re`, `pathlib`: 基本機能
