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
- **validated_suggestions**: 安全性情報（スコア、リスクレベル、承認ワークフロー）が付与された修正案のリスト。

### Core Logic
1.  **基本安全性チェック (`_check_basic_safety`)**:
    - 危険なキーワード（`delete`, `drop`, `exec`, `eval`, `unsafe` 等）が含まれていないか正規表現でスキャン。
    - 元のコードとの行数差（変更率）を計算し、大幅な変更がある場合はスコアを減点。
2.  **影響範囲分析 (`_analyze_impact_scope`)**:
    - `ASTAnalyzer` を用いて、クラス名やメソッド引数、戻り値型が変更されていないか（破壊的変更）をチェック。
    - 新しい依存関係（`using`, `import`）の追加を検出。
3.  **リスク評価 (`_assess_risk_level`)**:
    - 基本スコアに対し、破壊的変更がある場合は 50% 減点、依存関係変更がある場合は 20% 減点するなど調整。
    - 最終スコアに基づき `low`, `medium`, `high`, `critical` のリスクレベルを決定。
4.  **承認ワークフロー判定 (`_determine_approval_workflow`)**:
    - `low`: 自動適用可能。
    - `medium` 以上: 開発者やシニア開発者による承認を必須とする設定を付与。
5.  **フィルタリング**:
    - 致命的なリスクがある、または基本スコアが閾値（`risk_thresholds`）を下回る提案をリストから除外。
    - **例外**: `syntax_fix`, `test_self_healing`, `logic_gap_fix` などの修復的修正（Remedial Fix）は、スコアが低くても（> 0.4）リストに残す緩和措置を適用。

## 3. Dependencies
- **Internal**: `ast_analyzer`, `semantic_analyzer`
- **External**: `re`, `os`
