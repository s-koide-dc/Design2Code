# ActionSynthesizer Design Document

## 1. Purpose

`ActionSynthesizer` は IR ノードを具体的な合成経路へ落とす orchestration 層である。  
特に、`spec_role` を runtime execution intent に橋渡しし、`CHECK`, `FILTER`, `CALCULATE`, `DESERIALIZE` の metadata-driven dispatch を担う。

## 2. Structured Specification

### Input
- **Description**: 現在ノード、合成 path、任意の future hint、既消費 node ID 集合。
- **Type/Format**: `Dict[str, Any]`, `Dict[str, Any]`, `Optional[str]`, `Optional[set]`

### Output
- **Description**: 更新済み synthesis path 候補群。
- **Type/Format**: `List[Dict[str, Any]]`

### Core Logic
1. ノードから `spec_role` を読み、必要なら execution intent を補正する。
   - `DESERIALIZE` -> `JSON_DESERIALIZE`
   - `FILTER` -> `LINQ`
   - `DISPLAY` は弱い runtime intent を `DISPLAY` に補正する
2. `audit_only` や project ops を先に処理する。
3. `LOOP`, `CONDITION`, `RETURN`, `LINQ`, `CALC`, `DISPLAY/TRANSFORM` は専用 handler へ dispatch する。
4. `FETCH`, file persist, JSON, IO も専用 handler へ分岐する。
5. collection 入力で loop 展開が必要な場合は synthetic loop を生成する。
6. 一般アクションは candidate gathering -> 単一メソッド合成で処理する。
7. 候補が無い場合は fallback を試し、それでも無ければ `NotImplementedException` を生成する。
8. `CHECK` / `FILTER` / `CALCULATE` の詳細式や conservatism は binder/handler 側に委譲する。
9. debug 出力は通常経路では行わず、`NLP_DEBUG_STDOUT` が有効な場合のみ candidate gather や unresolved path の補助情報を出す。

### Test Cases
- **Happy Path**:
  - **Scenario**: `spec_role=FILTER` のノード。
  - **Expected Output**: `LINQ` handler に dispatch される。
- **Edge Cases**:
  - **Scenario**: 候補メソッドが無い。
  - **Expected Output / Behavior**: TODO 付き `NotImplementedException` を生成する。

## 3. Dependencies
- **Internal**:
  - `semantic_binder`
  - `statement_builder`
  - `action_handlers`
- **External**: なし

## 4. Operational Notes
- candidate gather や unresolved path の補助情報は `src.utils.stdout_guard.debug_print` を使う opt-in 出力とする。
- 通常の synthesis 経路では stdout を使わず、正式な結果は戻り値の synthesis path と generated code に集約する。
