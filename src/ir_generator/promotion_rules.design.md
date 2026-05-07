# promotion_rules Design Document

## 1. Purpose

`promotion_rules` は lexical baseline だけでは粗く分類されるステップを、追加条件付きで `FILTER` または `CALCULATE` へ昇格させる。安易なキーワード一致ではなく、logic と context を併用する。

## 2. Structured Specification

### Input
- **Description**: ステップ文、token 列、logic goals、history、output type hint、semantic roles、現在の intent。
- **Type/Format**: `str`, `List[Dict[str, Any]]`, `List[Dict[str, Any]]`, `Dict[str, Any]`

### Output
- **Description**: 昇格可否、補助 property 候補。
- **Type/Format**: `bool`, `Optional[str]`

### Core Logic
1. `has_filter_lexical_signal` は `抽出` / `選択` と `select` / `where` surface を検出する。
2. `has_filter_predicate_logic` は比較・文字列・論理 goal があるかを判定する。
3. `has_upstream_collection_context` は前段の collection 文脈を判定する。
4. `should_promote_to_filter` は、曖昧語彙 + predicate logic + upstream collection context の 3 条件がそろう場合のみ真にする。
5. `has_calculation_intent_signal` は `計算` / `算出` / `求める` を検出する。
6. `should_promote_to_calculate` は、target metadata が存在し、通知・check・map/select 系と競合しない場合のみ真にする。
7. `infer_filter_property` は goal hint または token 文脈から filter property を決定的に拾う。

### Test Cases
- **Happy Path**:
  - **Scenario**: `Points が 100 より大きいユーザーを抽出する`。
  - **Expected Output**: `FILTER` 昇格条件が真。
- **Edge Cases**:
  - **Scenario**: `ユーザーを抽出する` だけで predicate が無い。
  - **Expected Output / Behavior**: `FETCH` のまま残す。
  - **Scenario**: target metadata が無い計算語彙。
  - **Expected Output / Behavior**: `CALCULATE` に上げない。

## 3. Dependencies
- **Internal**: なし
- **External**: なし
