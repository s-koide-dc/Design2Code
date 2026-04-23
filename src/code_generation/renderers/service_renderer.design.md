# service_renderer Design Document

## 1. Purpose

`service_renderer` は Service クラスの C# ソースを生成する。

## 2. Structured Specification

### Input
- **Description**: Service 名、インターフェイス名、Repository インターフェイス名、メソッド定義（シグネチャと本文）、名前空間。
- **Type/Format**: `str`, `list`
- **Example**:
  ```json
  {
    "name": "OrderService",
    "methods": [["public Order GetById(int id)", ["return _repo.FetchById(id);"]]]
  }
  ```

### Output
- **Description**: Service クラスの C# ソースコード。
- **Type/Format**: `str`
- **Example**: `"public class OrderService : IOrderService { ... }"`

### Core Logic
1. `methods` を走査し、シグネチャと本文からメソッドブロックを組み立てる。
2. `using` と `namespace` を付与し、`repo_iface` を依存注入するクラスを生成する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 1 つ以上のメソッドを含む。
  - **Expected Output**: すべてのメソッドがクラス内に出力される。
- **Edge Cases**:
  - **Scenario**: メソッド本文が空配列。
  - **Expected Output / Behavior**: 空ブロックが生成される。

## 3. Dependencies
- **Internal**: なし
