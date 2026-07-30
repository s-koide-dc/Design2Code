# tests/ README

このディレクトリは、生成・解析・実行の品質を担保するテスト群を配置します。

## 1. テスト構成
- `unit/`  
  小さな単位のロジック検証。
- `integration/`  
  複数モジュールの連携検証。
- `security/`  
  セキュリティ/安全性の確認。
- `fixtures/`  
  テスト用素材（設定・サンプル資産）。
- `test_projects/`  
  解析や生成の対象となるプロジェクト素材。

## 2. 実行の考え方
- 日常は `unit` を優先的に回し、`integration` は必要時に追加します。
- **全体テスト**では `unit` と `integration` をまとめて実行します。
- `security` は運用前/変更時に重点的に実行します。

## 3. 実行例
```bash
# Unit
python -m unittest tests.unit.test_method_store

# Integration (例)
python -m unittest tests.integration.test_pipeline_core

# Full (unit + integration)
python -m unittest discover -s tests -p "test_*.py" -t .
```

## 4. 前提
- `resources/` 配下の辞書・ベクトルが必要なテストがあります。
- `resources/vectors` のキャッシュ未生成だと失敗するテストがあります。
- `resources/vectors` の実モデルが必要な integration テストがあります。
- GitHub Actions では実モデルを配置せず、モデル依存テストは `SKIP_VECTOR_MODEL=1` または対象スイート除外として扱います。ユニットテストランナーはスキップ件数を最後に表示します。
- integration テストのCI実行／ローカル実行境界は `tests/ci_test_matrix.json` で管理し、`scripts/validate/validate_ci_test_matrix.py` が除外対象の存在・理由・未分類テストを検証します。
- `test_regression_scenarios.py` は設計解決・監査に集中するためインプロセスのCodeBuilderフォールバックを使用します。外部.NET CodeBuilderとの連携は `test_code_synthesizer_integration.py` などの専用テストで検証します。
- `test_code_synthesizer_integration.py` の外部.NET CodeBuilderテストは `RUN_CODEBUILDER_TESTS=1` のときだけ有効です。通常のユニット実行ではスキップされ、生成品質ジョブで明示的に実行されます。
- `test_response_rewriter.py` のsubprocess／persistent subprocess／HTTPバックエンドテストは `RUN_RESPONSE_REWRITER_BACKENDS=1` のときだけ有効です。通常のユニット実行ではスキップされ、生成品質ジョブで明示的に実行されます。
- `test_execution_verifier.py` のRoslyn構造解析テストは `RUN_EXECUTION_VERIFIER_TESTS=1` のときだけ有効です。通常のユニット実行ではスキップされ、生成品質ジョブで明示的に実行されます。
- 実モデルを保持するローカル環境では [`docs/real_vector_model_validation.md`](../docs/real_vector_model_validation.md) の検証手順を実行します。
- 実モデル・辞書・method-store資産を保持する環境では `python scripts/validate/run_local_semantic_quality_gate.py` を実行します。このゲートはCIマトリクスで除外した統合テストをすべて実行します。
- モデル非依存のテストを明示的に実行する場合は `SKIP_VECTOR_MODEL=1` を設定します。
