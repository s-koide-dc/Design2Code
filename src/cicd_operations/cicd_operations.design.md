# CICDOperations Design Document

## 1. Purpose
`CICDOperations` は、独立したモジュールとして、CI/CDパイプラインのセットアップ、品質ゲートの設定、および設定ファイルの生成・統合を担当します。`CICDIntegrator` と連携し、プロジェクトの自動化と品質維持を支援します。

## 2. Structured Specification

### 2.1. 初期化 (`__init__`)
- **Parameters**: `action_executor` - 親となる ActionExecutor インスタンス (移行期間中)
- **Logic**: ActionExecutor への参照を保持し、`_get_entity_value` や `_safe_join` などのヘルパーメソッドにアクセスできるようにします。

### 2.2. パイプライン設定 (`setup_cicd_pipeline`)
- **Input**:
    - `project_name`: プロジェクト名
    - `language`: 言語 (default: csharp)
    - `ci_platform`: プラットフォーム (default: github_actions)
    - `quality_gates`: 品質ゲート設定
- **Core Logic**:
    1. `CICDIntegrator` を使用してパイプライン設定を生成します。
    2. 生成された設定ファイルを適切なパスに保存します。
- **Output**: 設定完了メッセージと保存されたファイルのリスト。

### 2.3. 品質ゲート構成 (`configure_quality_gates`)
- **Input**: `coverage_threshold`, `quality_score_threshold` 等のしきい値。
- **Core Logic**:
    1. 言語に応じた品質ゲートのしきい値を設定します。
    2. `CICDIntegrator.setup_quality_gates` を呼び出して反映します。
- **Output**: 設定されたゲートの数と種類のサマリー。

### 2.4. CI/CD設定生成 (`generate_cicd_config`)
- **Input**: プロジェクト名、言語、プラットフォーム情報。
- **Core Logic**:
    1. **レポート自動検索**: `test_reports`, `coverage_reports`, `refactoring_reports` ディレクトリを走査し、最新の JSON レポートを自動的に特定します。
    2. **統合品質レポートの生成**: 抽出された複数のレポートを `CICDIntegrator` で一つの構造化データにまとめます。
    3. **設定ファイルへの反映**: 統合レポートを含む CI/CD 設定ファイルを生成します。
- **Output**: 統合されたレポートの内容と、生成されたファイルリスト。

### 2.5. 品質ゲートチェック (`check_quality_gates`)
- **Input**: `metrics_file` (任意), `gates_config` (任意)
- **Core Logic**:
    1. **ゲート検証**: `QualityGateChecker` を実行し、カバレッジや品質スコアがしきい値を満たしているかチェックします。
    2. **自律的整合性監査**: `AutonomousAligner` を起動し、`VectorEngine` を用いて設計書と実装のセマンティックな不整合（乖離）を監査します。
    3. **総合ステータス判定**: ゲートの成否と整合性監査の結果を組み合わせ、`passed`, `warning`, `failed` のいずれかのステータスを返します。
- **Output**: 各ゲートの通過状況、および詳細な整合性レポート。

## 3. Dependencies
- **Internal**: `ActionExecutor` (移行用依存), `CICDIntegrator`, `QualityGateChecker`, `AutonomousAligner`
- **External**: `os`, `typing`, `json`

## 4. Error Handling
- 設定ファイル書き込み時の権限エラーやパス不備
- インテグレーター実行時の例外キャッチと報告
