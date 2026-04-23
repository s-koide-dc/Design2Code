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
