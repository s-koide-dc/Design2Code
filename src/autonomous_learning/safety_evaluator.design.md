# SafetyEvaluator Design Document

## 1. Purpose
`SafetyEvaluator` は、`PatternLearner` が検証した改善ルールに添付された
構造化安全レビューを確認するモジュールです。ルール本文のキーワードや
係数スコアから安全性を推測しません。

## 2. Structured Specification

### 2.1. 安全性評価フロー (`evaluate_suggestions`)
- **Input**: `suggestions` (List[RuleSuggestion]) - 学習されたルール提案のリスト。
- **Logic**:
  1. 提案の `risk_level` が設定の `allowed_risk_levels` に含まれることを確認します。
  2. `safety_evidence.reviewed` が `true` であることを確認します。
  3. `safety_evidence.decision` が `approve` であることを確認します。
  4. 1件以上のcontrolがあり、各controlに `control_id` と `passed: true` があることを確認します。
  5. 不足・拒否・control失敗は `evaluation_diagnostics` に理由を記録して除外します。

## 3. Dependencies
- `PatternLearner`: ルール提案の定義
- `logging`, `typing`: 基本機能

## 4. Operational Logging
- 安全性制約による提案拒否は期待されたポリシー判断なので `INFO` とする。
- 評価処理自体の障害と設定破損のみをwarning/error対象とし、正常拒否でテスト・運用ログを汚染しない。

## 5. Review Notes
- 2026-06-30: 正常な安全性拒否のログレベルをINFOへ同期。
