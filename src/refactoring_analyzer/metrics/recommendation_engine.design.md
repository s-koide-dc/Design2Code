# RecommendationEngine Design Document

## 1. Purpose
`RecommendationEngine` は、分析結果に基づき、プロジェクト管理者や開発者が次に取るべき具体的なアクション（修正の優先順位、予防措置、自動化の活用等）を提案します。

## 2. Structured Specification

### Input
- **smell_result**: 検出されたスメルの統計。
- **suggestions**: リファクタリング提案。
- **quality_metrics**: 品質スコア等のメトリクス。

### Output
- **recommendations**: カテゴリ化された推奨事項のリスト。

### Core Logic
1.  **即座のアクション推奨**: 高優先度の提案がある場合、品質スコア向上への期待効果（1件あたり +0.5ポイント等）を含めて修正を推奨。
2.  **予防措置推奨**: 改善ポテンシャルが「High」の場合、将来の負債蓄積を防ぐためのレビューガイドライン強化等を提案。
3.  **自動化の活用推奨**: 自動修正可能な項目がある場合、短縮可能な工数を提示して実行を促す。
4.  **優先順位付け**: リスクレベルと改善効果のバランスに基づき、アクションをカテゴリ化して提示。

## 3. Dependencies
- **External**: `typing`
