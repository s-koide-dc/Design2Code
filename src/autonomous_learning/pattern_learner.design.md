# PatternLearner Design Document

## 1. Purpose
`PatternLearner` は、抽出された対話パターンやエラーパターンを、具体的な「改善ルール（Rule Suggestion）」へと変換するモジュールです。成功体験からは意図検出の強化ルールを、失敗体験からは自動リトライや明確化の戦略を学習します。

## 2. Structured Specification

### 2.1. ルール学習フロー (`learn_from_patterns`)
- **Input**: `patterns` (Dict[str, List[LearningPattern]]) - `LogAnalyzer` により抽出されたパターンの辞書。
- **Logic**:
  1. **成功パターンからの学習**: 頻出する意図検出の成功例（信頼度 0.7 以上）を元に、`intent_rule`（正規表現パターン）を生成します。
  2. **エラーパターンからの学習**: 2回以上発生した同一タイプのエラーに対し、指数バックオフ等を含む `retry_rule` を生成します。
  3. **改善機会からの学習**: 意図検出の失敗や頻繁な聞き返しが発生している入力に対し、より適切な `clarification_rule`（明確化メッセージの改善等）を生成します。
  4. **明確化復帰パターン**: ユーザーの訂正によって成功した事例から、既存の誤認を修正する `intent_rule` を生成します。

### 2.2. 競合チェック (`_check_rule_conflicts`)
- 新しいルール提案が既存の定義と矛盾しないか、または既に存在していないかを検証します。

## 3. Dependencies
- `LogAnalyzer`: パターン情報の提供元
- `dataclasses`, `logging`, `typing`: 基本機能
