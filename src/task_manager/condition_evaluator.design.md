# ConditionEvaluator Design Document

## 1. Purpose
`ConditionEvaluator` は、タスクの状態遷移条件（例：特定のエンティティが存在するか、意図が一致するか）をコンテキストに基づいて評価します。

## 2. Structured Specification

### Input
- **condition**: 評価条件（辞書形式または文字列）。
- **context**: パイプライン・コンテキスト。

### Core Logic
1.  **型判定**: 文字列（"true"/"false"）または辞書（構造化条件）を判定。
2.  **条件タイプの処理**:
    - `always_true`: 常に真を返す。
    - `entity_exists`: コンテキストの `analysis/entities` または `task/parameters` に指定キーが存在するか（かつ値が空でないか）を確認。
    - `entity_value_is`: 指定キーの値が期待値と完全一致するか比較。
    - `intent_is`: 現在の意図（intent）が指定値と一致するか確認。
    - **論理結合**:
        - `all_of`: `predicates` 内のすべての条件が真の場合に真を返す (AND)。
        - `any_of`: `predicates` 内のいずれかの条件が真の場合に真を返す (OR)。

### Test Cases
- **Scenario**: Happy Path - Entity Exists
    - **Input**: condition={'type': 'entity_exists', 'key': 'location'}, context={'analysis': {'entities': {'location': 'Tokyo'}}}
    - **Expected**: True
- **Scenario**: Happy Path - Entity Value Is
    - **Input**: condition={'type': 'entity_value_is', 'key': 'confirm', 'value': 'yes'}, context={'analysis': {'entities': {'confirm': 'yes'}}}
    - **Expected**: True
- **Scenario**: Edge Case - Missing Key
    - **Input**: condition={'type': 'entity_exists', 'key': 'missing'}, context={'analysis': {'entities': {}}}
    - **Expected**: False
- **Scenario**: Logic - All Of (AND)
    - **Input**: condition={'type': 'all_of', 'predicates': [{'type': 'always_true'}, {'type': 'always_true'}]}, context={}
    - **Expected**: True
- **Scenario**: Logic - Any Of (OR)
    - **Input**: condition={'type': 'any_of', 'predicates': [{'type': 'always_true'}, {'type': 'entity_exists', 'key': 'missing'}]}, context={}
    - **Expected**: True

## 3. Dependencies
- なし
