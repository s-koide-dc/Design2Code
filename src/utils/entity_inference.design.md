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
1. history がある場合は `context_entity` を直前 `target_entity` から初期化する。
2. morph analyzer がある場合は token の base/surface を取得する。
3. entity schema の各 entity について `keywords` を走査し、token または lower text と一致した最初の entity を返す。
4. 一致が無い場合、`allow_history_fallback=True` なら強い context entity を返す。
5. schema 上の entity が 1 つだけなら、その entity を返す。
6. それ以外は `allow_history_fallback` の設定に応じて `context_entity` または `Item` を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: schema keyword と文面が一致する。
  - **Expected Output**: 対応 entity を返す。
- **Edge Cases**:
  - **Scenario**: keyword 一致なし、history fallback 無効。
  - **Expected Output / Behavior**: `Item` を返す。

## 3. Dependencies
- **Internal**: なし
- **External**: なし
