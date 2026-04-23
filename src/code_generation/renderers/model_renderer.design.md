# model_renderer Design Document

## 1. Purpose

`model_renderer` は Entity/DTO/Interface の C# ソースを生成する。

## 2. Structured Specification

### Input
- **Description**: クラス名、プロパティ一覧、DTO マッピング、名前空間など。
- **Type/Format**: `str`, `list`, `dict`, `bool`
- **Example**:
  ```json
  {
    "name": "Order",
    "props": [["Id","int"],["Total","decimal"]]
  }
  ```

### Output
- **Description**: Entity/DTO/Interface の C# ソースコード。
- **Type/Format**: `str`
- **Example**: `"public class Order { public int Id { get; set; } }"`

### Core Logic
1. `props` を走査し、`string` 型は `required` を付与する。
2. DTO の場合、`has_from` が真なら `FromEntity` を生成する。
3. DTO の場合、`has_to` が真なら `ToEntity` を生成し、`UtcNow` マッピングを特別扱いする。
4. Interface の場合はメソッドシグネチャに `;` を付与して出力する。

### Test Cases
- **Happy Path**:
  - **Scenario**: Entity と DTO を生成する。
  - **Expected Output**: `Models` / `DTO` 名前空間のクラスが生成される。
- **Edge Cases**:
  - **Scenario**: DTO マッピングが空。
  - **Expected Output / Behavior**: 変換メソッドが空のまま生成される。

## 3. Dependencies
- **Internal**: なし
