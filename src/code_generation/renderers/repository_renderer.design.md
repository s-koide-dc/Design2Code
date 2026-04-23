# repository_renderer Design Document

## 1. Purpose

`repository_renderer` は Repository クラスの C# ソースを生成する。

## 2. Structured Specification

### Input
- **Description**: Repository 名、インターフェイス名、メソッド定義（シグネチャと本文）、名前空間。
- **Type/Format**: `str`, `list`
- **Example**:
  ```json
  {
    "name": "OrderRepository",
    "methods": [["public Order FetchById(int id)", ["return _db.QuerySingle<Order>(sql, new { id });"]]]
  }
  ```

### Output
- **Description**: Repository クラスの C# ソースコード。
- **Type/Format**: `str`
- **Example**: `"public class OrderRepository : IOrderRepository { ... }"`

### Core Logic
1. `methods` を走査し、シグネチャと本文からメソッドブロックを構成する。
2. Dapper/IDbConnection の `using` を含め、クラス雛形を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: CRUD メソッドを含む。
  - **Expected Output**: すべてのメソッドがクラス内に出力される。
- **Edge Cases**:
  - **Scenario**: 本文が空のメソッド。
  - **Expected Output / Behavior**: 空ブロックが生成される。

## 3. Dependencies
- **Internal**: なし
