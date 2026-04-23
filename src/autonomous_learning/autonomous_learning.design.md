# autonomous_learning Design Document

## 1. Purpose (Updated 2026-04-21 13:15)

`AutonomousLearning` はログ分析とパターン学習を通じて、意図ルールやリトライルールを自動更新する。  
修復知識や構造メモリ、コンプライアンス監査も統合する。

## 2. Structured Specification

### Input
- **Description**: イベント種別とデータ、ログディレクトリ。
- **Type/Format**: `str`, `Dict[str, Any]`

### Output
- **Description**: 学習結果、提案、適用件数。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. 設定を読み込み、`LogAnalyzer` / `PatternLearner` / `SafetyEvaluator` / `EventProcessor` を初期化する。
2. `ConfigManager.storage_dir`（`resources/vectors/vector_db`）を `RepairKnowledgeBase` / `StructuralMemory` の統一保存先として使用する。
3. 旧配置（ワークスペース直下 / `resources` / `cache`）にある `repair_knowledge_meta.json` / `repair_knowledge_vectors.npy` と `structural_memory_meta.json` / `structural_memory_vectors.npy` は、起動時に統一保存先へ移行する。
4. `trigger_learning` はイベントを同期/非同期で処理する。
5. `run_learning_cycle` はログを収集し、パターン抽出 → 提案生成 → 安全評価 → 適用を行う。
6. 学習サイクル内で修復知識学習、辞書マッピング統合、構造メモリ索引、コンプライアンス監査を実行する。
7. `apply_suggestions` は意図ルールとリトライルールを更新する。
8. `generate_knowledge_summary` は修復知識とコンプライアンスの概要を返す。

## 4. Review Notes
- 2026-04-21: `StructuralMemory` 旧配置の移行対象に `resources` 直下も追加し、重複保存の自動整理を強化。
- 2026-04-21: `RepairKnowledgeBase` も `config_manager.storage_dir` を使用するよう更新し、ベクトルDB保存先を `resources/vectors/vector_db` に統一。

### Test Cases
- **Happy Path**:
  - **Scenario**: 十分なログがあり学習が成功する。
  - **Expected Output**: `status == "success"`。
- **Edge Cases**:
  - **Scenario**: ログが少ない。
  - **Expected Output / Behavior**: `status == "skipped"`。

## 3. Dependencies
- **Internal**: `log_analyzer`, `pattern_learner`, `event_processor`, `safety_evaluator`, `structural_memory`, `compliance_auditor`, `repair_knowledge_base`, `config_manager`, `vector_engine`
- **External**: `json`, `threading`, `pathlib`, `logging`
