# QualityGateChecker Design Document

## 1. Purpose
`QualityGateChecker` は、CI/CD パイプラインの一部として動作し、テスト結果、カバレッジ、コード品質メトリクスが事前に定義された基準（ゲート）を満たしているかを検証します。

## 2. Structured Specification

### Input
- **metrics_file** (Optional): 解析済みのメトリクスを含む JSON ファイル。
- **gates_config** (Optional): 品質基準の定義。

### Output
- **gate_result**: 各ゲートの成否、全体ステータス（passed/failed/warning/error）、サマリー。

### Core Logic
1.  **メトリクスの収集 (`_collect_metrics`)**: 
    - `TRX` や `JUnit XML` ファイルをスキャンしてテスト通過状況を確認。
    - `Cobertura XML` や `coverage.json` からカバレッジ率を取得。
    - リファクタリングレポートから品質スコアとスメル件数を抽出。
2.  **ゲート評価**: 
    - `QualityGateManager` を用いて、各基準（例: カバレッジ > 80%）を評価。
    - `blocking` タイプのゲートが失敗した場合は、全体ステータスを `failed` に設定。
3.  **レポート出力**: 検証結果をテキストまたは JSON 形式で出力。

## 3. Dependencies
- **Internal**: `cicd_integrator`
- **External**: `xml.etree.ElementTree`, `glob`, `json`
