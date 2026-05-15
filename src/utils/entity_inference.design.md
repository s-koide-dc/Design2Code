# entity_inference Design Document

## 1. Purpose

`entity_inference` は自然文と entity schema から target entity を決定的に推定する。history 継承は許可/禁止を切り替え可能で、`CALCULATE` の resolution 段と一般の entity 推定を分離するために使う。

## 2. Structured Specification

### Input
- **Description**: ステップ文、history、entity schema、任意の morph analyzer、history fallback 許可フラグ。
- **Type/Format**: `str`, `list`, `Dict[str, Any]`, `bool`

### Output
- **Description**: 推定 target entity。
- **Type/Format**: `str`

### Core Logic
1. history がある場合は `context_entity` を直前 `target_entity` から初期化し、loop item continuity がある場合は `item_entity` も読む。
2. morph analyzer がある場合は token の base/surface を取得する。
3. entity schema の各 entity について `keywords` を走査し、token または lower text と一致した最初の entity を返す。
4. 一致が無い場合、`allow_history_fallback=True` なら `item_entity` を `target_entity` より優先して返す。
5. それでも無ければ強い context entity を返す。
6. schema 上の entity が 1 つだけなら、その entity を返す。
7. それ以外は `allow_history_fallback` の設定に応じて `context_entity` または `Item` を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: schema keyword と文面が一致する。
  - **Expected Output**: 対応 entity を返す。
- **Edge Cases**:
  - **Scenario**: keyword 一致なし、history fallback 無効。
  - **Expected Output / Behavior**: `Item` を返す。

## 5. Notes
- loop node が `iteration_item_entity` / `iteration_item_var` を `context history` に残している場合、nested child の entity inference は item entity continuity を通常の `target_entity` history より優先し、downstream は同じ loop item alias を維持しやすくなる。

## 3. Dependencies
- **Internal**: なし
- **External**: なし
