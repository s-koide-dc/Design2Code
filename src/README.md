# src/ README

このディレクトリは、ローカル AI の **コア実装** を保持します。  
生成・解析・パイプライン・検証がここに集約されています。

## 1. 入口
- パイプライン入口: `C:\workspace\NLP\src\pipeline_core\pipeline_core.py`
- 設計書→プロジェクト生成: `C:\workspace\NLP\src\code_generation\project_generator.py`
- 設計書→コード合成: `C:\workspace\NLP\src\code_synthesis\code_synthesizer.py`

## 1.1 設計書→生成の最短パス
1. `design_parser` が `.design.md` を StructuredSpec に変換
2. `ir_generator` が IR を生成
3. `code_synthesis` がブループリントを生成
4. `CodeBuilder` が C# を出力

## 2. 主要モジュール
- 解析: `morph_analyzer`, `syntactic_analyzer`, `semantic_analyzer`, `intent_detector`
- 生成: `ir_generator`, `code_synthesis`, `code_generation`, `test_generator`
- 実行: `action_executor`, `task_manager`, `planner`, `response_generator`
- 品質: `coverage_analyzer`, `refactoring_analyzer`, `cicd_integrator`, `code_verification`
- 学習/整合: `autonomous_learning`, `autonomous_aligner`, `replanner`

## 3. 重要な内部データ
`src` は `C:\workspace\NLP\resources` と `C:\workspace\NLP\config` に依存します。
- `resources`: 辞書・ベクトル・知識ベース
- `config`: 安全性・生成方針・運用設定

## 4. 決定性に影響する要因
- `resources/method_store.json` と `resources/vectors/vector_db/*`
- `resources/vectors/chive-1.3-mc90.txt` と対応キャッシュ
- `cache/blueprints/<run_id>/blueprint.json`
- `config` 内のルール (`project_rules.json`, `retry_rules.json`)
