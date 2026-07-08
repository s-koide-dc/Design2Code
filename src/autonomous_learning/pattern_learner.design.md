# PatternLearner Design Document

## 1. Purpose
`PatternLearner` は、承認済みの構造化学習根拠に含まれる
`proposed_rule` を検証し、具体的な `RuleSuggestion` へ変換するモジュールです。
頻度、信頼度、入力文字列からルール内容を推測しません。

## 2. Structured Specification

### 2.1. ルール学習フロー (`learn_from_patterns`)
- **Input**: `patterns` (Dict[str, List[LearningPattern]]) - `LogAnalyzer` により抽出されたパターンの辞書。
- **Logic**:
  1. 各パターンの `context.proposed_rule` がobjectであることを確認します。
  2. カテゴリごとの `rule_type`、非空の `rule_definition`、`impact_scope`、
     `risk_level`、`explanation` を検証します。
  3. `supporting_evidence` が指定された場合はobject配列であることを検証します。
  4. `safety_evidence` がobjectとして添付されていることを検証します。
  5. 検証済みの値を変更せず `RuleSuggestion` へ変換します。
  6. 不正な提案は生成せず、理由を `validation_diagnostics` に記録します。

## 3. Dependencies
- `LogAnalyzer`: パターン情報の提供元
- `dataclasses`, `logging`, `typing`: 基本機能
