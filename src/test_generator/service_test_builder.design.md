# service_test_builder Design Document

## 1. Purpose

`service_test_builder` はサービス層テストの生成に必要なコンテキストを組み立てる。

## 2. Structured Specification

### Input
- **Description**: サービス/リポジトリ名、CRUD テンプレート、バリデーション、型情報、設計書の Test Cases など。
- **Type/Format**: `str`, `dict`, `Dict[str, str]`, `List[str]`
- **Example**:
  ```json
  {
    "service_name": "OrderService",
    "crud_template": { "List": { "Service": "Get{EntityPlural}" } }
  }
  ```

### Output
- **Description**: テスト生成用のコンテキスト辞書。
- **Type/Format**: `Dict[str, str]`
- **Example**: `{ "ServiceClass": "OrderService", "ListMethod": "GetOrders" }`

### Core Logic
1. ルールから有効な DTO 値を構築する。
2. ルールが存在する場合は無効入力テストを生成する。
3. CRUD テンプレートからメソッド名を組み立てる。
4. `Test Cases` が構造化 JSON の場合は `StructuredTestCases` としてコンテキストに格納する。
5. 返却用のテストコンテキスト辞書を構築する。

### Test Cases
- **Happy Path**:
  - **Scenario**: バリデーション規則あり。
  - **Expected Output**: `InvalidTest` を含むコンテキストが返る。
- **Edge Cases**:
  - **Scenario**: ルールが無い。
  - **Expected Output / Behavior**: `InvalidTest` が空文字になる。

## 3. Dependencies
- **Internal**: `test_generator`
