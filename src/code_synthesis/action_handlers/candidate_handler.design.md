# candidate_handler Design Document

## 1. Purpose

`candidate_handler` はアクション候補の収集を担当し、必要に応じて知識ベース検索を行う。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、対象ノード、パス、ターゲットエンティティ。
- **Type/Format**: `Dict[str, Any]`, `str`
- **Example**: `target_entity="Order"`

### Output
- **Description**: 候補アクションの配列。
- **Type/Format**: `List[Dict[str, Any]]`
- **Example**: `[{"intent":"FETCH","method":"GetOrders"}]`

### Core Logic
1. `action_synthesizer._gather_candidates` を実行する。
2. 候補が空で `ukb` が利用可能なら `ukb.search` を呼ぶ。
3. 例外が発生した場合は空配列にフォールバックする。

### Test Cases
- **Happy Path**:
  - **Scenario**: 内部候補が取得できる。
  - **Expected Output**: 候補がそのまま返る。
- **Edge Cases**:
  - **Scenario**: 内部候補が空、`ukb` 検索で例外。
  - **Expected Output / Behavior**: 空配列が返る。

## 3. Dependencies
- **Internal**: `code_synthesis`
