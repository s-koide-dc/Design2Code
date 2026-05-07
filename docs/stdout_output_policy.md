# Stdout Output Policy

## Purpose

この文書は、プロジェクト内の出力経路を

- `Formal CLI stdout`
- `Formal CLI stderr`
- `debug_print`
- `logger`

の 4 種類に分けて固定するための運用基準である。

目的は、内部診断と利用者向け出力を混在させないこと、
および今後の変更時に `print` の追加を設計判断なしに行わせないことにある。

## Canonical Rules

### 1. Formal CLI stdout

利用者が直接受け取る正式結果だけを出す。

対象:

- REPL の対話応答
- CI / CLI の最終レポート
- JSON 形式の正式出力

条件:

- 返り値や `context["response"]["text"]` と整合していること
- 同じ情報を logger にしか出さない、または debug にしか出さない、という分裂を作らないこと

### 2. Formal CLI stderr

CLI 実行時の補助診断や異常系だけを出す。

対象:

- 設定ファイル読込失敗
- メトリクス収集失敗
- REPL 実行時の予期しない例外

条件:

- 利用者向けの正式結果と混在しないこと
- 正常系メッセージを stderr に出さないこと

### 3. `debug_print`

手動検証、PoC、候補トレース、サンプル実行など、
通常利用では不要だが開発時に有用な補助出力だけを扱う。

条件:

- `NLP_DEBUG_STDOUT=1` のときだけ出ること
- 標準利用時に無音であること
- 進行表示や候補列挙はここへ寄せること

### 4. `logger`

内部診断、読込失敗、回復処理、補助的な警告を扱う。

条件:

- API やモジュールの返り値契約を汚さないこと
- CLI 正式出力の代替にしないこと
- 失敗情報は logger と戻り値の両方が必要かを明示的に判断すること

## Current Classification

### Formal CLI stdout

- `src/pipeline_core/pipeline_core.py`
  - `_emit_repl_response`
- `src/cicd_integrator/quality_gate_checker.py`
  - `_emit_stdout`
  - `print_results`
  - `--format json` の標準出力

### Formal CLI stderr

- `src/pipeline_core/pipeline_core.py`
  - `_emit_repl_error`
- `src/cicd_integrator/quality_gate_checker.py`
  - `_emit_stderr`

### `debug_print`

主な対象:

- `src/ir_generator/ir_generator.py`
- `src/code_synthesis/action_synthesizer.py`
- `src/code_synthesis/autonomous_synthesizer.py`
- `src/autonomous_learning/structural_memory.py`
- `src/advanced_tdd/main.py`
- `src/morph_analyzer/morph_analyzer.py`
- `src/syntactic_analyzer/syntactic_analyzer.py`
- `src/clarification_manager/clarification_manager.py`
- `src/utils/design_doc_parser.py`
- `src/utils/nuget_client.py`
- `src/autonomous_aligner/autonomous_aligner.py`
- `src/code_generation/project_generator.py`
- `src/code_verification/execution_verifier.py`
- `src/replanner/replanner.py`
- `src/utils/design_doc_refiner.py`

### `logger`

主な対象:

- `src/intent_detector/intent_detector.py`
- `src/vector_engine/vector_engine.py`
- `src/code_synthesis/knowledge_extractor.py`
- `src/log_manager/log_manager.py`
- `src/code_synthesis/template_registry.py`
- `src/code_synthesis/unified_knowledge_base.py`
- `src/response_generator/response_generator.py`
- `src/tdd_operations/tdd_operations.py`
- `src/utils/design_sync_util.py`
- `src/code_verification/sandbox_provisioner.py`
- `src/code_generation/service_generation.py`
- `src/utils/code_builder_client.py`

## Decision Rules For Future Changes

### When adding new output

1. まずそれが正式結果か内部診断かを決める
2. 正式結果なら stdout / stderr のどちらかを選ぶ
3. 内部診断なら `debug_print` と `logger` のどちらかを選ぶ
4. 判断理由を対応する `.design.md` に反映する

### Use `debug_print` when

- 手動検証のための一時的な観測が必要
- 候補一覧やスコアを目視したい
- 通常利用では不要

### Use `logger` when

- 読込失敗や内部例外を残したい
- 呼び出し元は戻り値で制御し、観測だけ別に残したい
- 標準出力に出すべきではない

### Do not do

- 内部失敗を何となく `print` する
- 同じ情報を stdout と logger に二重出力する
- `debug_print` を正式結果として使う
- 利用者向け正常結果を stderr に出す

## Minimal Review Checklist

- 新しい `print` は正式 CLI helper 内だけか
- 補助出力は `debug_print` か `logger` に寄っているか
- `.design.md` が最新の出力契約を説明しているか
- `validate_project_consistency.py` が通るか
