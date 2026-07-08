# SafetyValidator Design Document

## 1. Purpose
`SafetyValidator` は、生成されたコード修正案がシステムに与える副作用やリスクを評価し、安全に自動適用できるか、あるいは人間のレビューが必要かを判定するゲートキーパーの役割を担います。

## 2. Structured Specification

### Input
- **Constructor**:
    - `config` (Dict): 動作設定。
    - `semantic_analyzer` (Optional): 意味解析器。
    - `ast_analyzer` (Optional): AST解析器。
- **Method `validate_fix_safety`**:
    - **suggestions**: `CodeFixSuggestion` オブジェクトのリスト。
    - **target_code**: 修正対象の現在のコード情報。

### Output
- **validated_suggestions**: 安全性情報（リスクレベル、承認ワークフロー、判定根拠）が付与された修正案のリスト。
- `safety_score` は既存 API 互換の表示値として保持するが、適用可否の根拠には使わない。

### Core Logic
1.  **基本安全性チェック (`_check_basic_safety`)**:
    - 修正コード本文を正規表現、キーワード、変更量スコアで推定評価しない。
    - `suggestion.impact_analysis.safety_evidence.blocking_risks` に明示されたブロッキング根拠がある場合のみ基本安全性を不合格にする。
2.  **影響範囲分析 (`_analyze_impact_scope`)**:
    - `ASTAnalyzer` を用いて、クラス名やメソッド引数、戻り値型が変更されていないか（破壊的変更）をチェック。
    - C# は Roslyn 等の構造化解析結果がない場合、破壊的変更を推定しない。
    - 新しい依存関係や任意のリスク要因は、`safety_evidence` または `impact_analysis` に明示された情報のみ採用する。
3.  **リスク評価 (`_assess_risk_level`)**:
    - スコア閾値や減点ルールでリスクレベルを推定しない。
    - `safety_evidence.risk_level` または `impact_analysis.risk_level` が明示されていれば採用し、なければ `unclassified` とする。
    - `blocking_risks` があれば `decision = reject`、`requires_approval` があれば `decision = review`、それ以外は `decision = accept` とする。
4.  **承認ワークフロー判定 (`_determine_approval_workflow`)**:
    - `accept`: 承認不要。
    - `review`: 開発者レビューを要求。
    - `reject`: 開発者、シニア開発者、アーキテクトの確認が必要な却下候補として扱う。
5.  **フィルタリング**:
    - `blocking_risks` が明示された提案のみ除外する。
    - 修正タイプやスコアによる例外的な緩和措置は設けない。

## 3. Dependencies
- **Internal**: `ast_analyzer`, `semantic_analyzer`
- **External**: `os`
