# SafetyEvaluator Design Document

## 1. Purpose
`SafetyEvaluator` は、`PatternLearner` が生成した改善ルールの「安全性」を、事前定義されたポリシーとスコアリングロジックに基づいて評価するモジュールです。システムに悪影響を及ぼす可能性のあるルールの自動適用を阻止し、リスクレベル（Low, Medium, High）を判定します。

## 2. Structured Specification

### 2.1. 安全性評価フロー (`evaluate_suggestions`)
- **Input**: `suggestions` (List[RuleSuggestion]) - 学習されたルール提案のリスト。
- **Logic**:
  1. 各提案に対し、`_calculate_safety_score` を用いて 0.0 〜 1.0 のスコアを算出します。
  2. スコアに基づき、リスクレベル（0.8以上: Low, 0.6以上: Medium, それ未満: High）を決定します。
  3. `_passes_safety_constraints` を呼び出し、以下の制約をチェックします。
     - リスクレベルが `High` のものは一律却下。
     - ルール定義内に `dangerous_keywords`（delete, format等）が含まれる場合は却下。
  4. 制約をパスした「安全な」提案のみをリストとして返します。

### 2.2. スコアリングロジック (`_calculate_safety_score`)
- 基準スコアを 1.0 とし、以下の係数を乗算します。
  - **タイプ係数**: 意図ルール（0.95）、明確化ルール（0.98）、リトライルール（0.7）。
  - **信頼度係数**: 学習時の `confidence`。
  - **影響範囲係数**: 全体的（0.5）、ユーザー体験（0.9）、意図検出（0.95）。

## 3. Dependencies
- `PatternLearner`: ルール提案の定義
- `json`, `logging`, `typing`: 基本機能
