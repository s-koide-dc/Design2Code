# io_handler Design Document

## 1. Purpose

`io_handler` は IO 系ノードに対して候補を評価し、合成またはフォールバックを実行する。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、対象ノード、パス。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: IO 処理後のパス配列。
- **Type/Format**: `List[Dict[str, Any]]`

### Core Logic
1. `gather_candidates` で候補を取得する。
2. `steps` を持つ候補は HTN として `_process_htn_plan` に渡す。
3. 通常候補は `_synthesize_single_method` で合成する。
4. 結果が空の場合は `apply_fallbacks` を試す。
5. file persist shortcut の `PERSIST` 判定と statement intent には `src.utils.semantic_intents` の共通定数を使う。
6. file persist shortcut の `error_policy=return_default` では `WriteGeneratedTextFile(path, contents)` helper を呼び、失敗時は `StatementBuilder._catch_action_for_policy()` と同じ fallback return を呼び出し元で実行する。success flag は制御用 raw local とし、dataflow の `out_var` には登録しない。
7. `error_policy=continue/rethrow` の file persist は structured resilient wrapper を使う。

### Test Cases
- **Happy Path**:
  - **Scenario**: 候補が存在する。
  - **Expected Output**: 合成結果が返る。
  - **Scenario**: `source_kind=file` の persist shortcut。
  - **Expected Output**: text file write helper call と failure guard が生成される。
- **Edge Cases**:
  - **Scenario**: 候補が空でフォールバックが有効。
  - **Expected Output / Behavior**: フォールバック結果が返る。

## 3. Dependencies
- **Internal**: `code_synthesis`

## 4. Review Notes
- 2026-06-04: `PERSIST` file shortcut の intent 判定と statement metadata を `src.utils.semantic_intents` の共通語彙へ寄せた。
- 2026-07-13: file persist の `return_default` 経路を `WriteGeneratedTextFile` helper と failure guard に寄せる契約へ同期。
