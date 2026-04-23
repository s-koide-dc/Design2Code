# service_test_generator Design Document

## 1. Purpose

`service_test_generator` はサービス層の単体テストコードを文字列として生成する。

## 2. Structured Specification

### Input
- **Description**: テスト用コンテキストとルート名前空間。
- **Type/Format**: `Dict[str, Any]`, `str`
- **Example**: `root_namespace="OrdersProject"`

### Output
- **Description**: xUnit テストコード。
- **Type/Format**: `str`
- **Example**: `"public class OrderServiceTests { ... }"`

### Core Logic
1. `FakeRepo` 実装を生成し、CRUD 呼び出しを差し込む。
2. 既定のテスト（空リスト、NotFound、削除失敗）を生成する。
3. Happy Path のテスト（Create 成功、GetById 成功、Update 成功、削除成功）を生成する。
4. `StructuredTestCases` があれば、JSON 形式の `arrange` / `act` / `assert` をそのままテストとして生成する。
5. `InvalidTest` があれば挿入する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 典型的な CRUD コンテキスト。
  - **Expected Output**: FakeRepo と複数テストが生成される。
- **Edge Cases**:
  - **Scenario**: `InvalidTest` が空。
  - **Expected Output / Behavior**: その部分が省略される。

## 3. Dependencies
- **Internal**: `test_generator`
