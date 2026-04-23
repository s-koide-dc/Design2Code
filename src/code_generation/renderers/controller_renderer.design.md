# controller_renderer Design Document

## 1. Purpose

`controller_renderer` はルート定義に基づいて ASP.NET Core Controller のソースコードを生成する。

## 2. Structured Specification

### Input
- **Description**: Controller 名、サービスインターフェイス、ルート一覧、アクション名/呼び出しマッピング、DTO/ID 型、名前空間、バリデーションガード。
- **Type/Format**: `str`, `list`, `dict`, `list | None`
- **Example**:
  ```json
  {
    "name": "OrdersController",
    "routes": ["GET /orders", "POST /orders"],
    "action_names": { "list": "GetOrders" }
  }
  ```

### Output
- **Description**: Controller クラスの C# ソースコード。
- **Type/Format**: `str`
- **Example**: `"public class OrdersController : ControllerBase { ... }"`

### Core Logic
1. ルート配列を走査し、HTTP メソッドとパスから属性（`HttpGet/HttpPost/HttpPut/HttpDelete`）を決定する。
2. `{id}` を含むパスは ID 引数付きアクションを生成し、その他は `list/create` を生成する。
3. `validation_guards` がある場合は Create/Update の本文先頭へ挿入する。
4. サービス呼び出しと `IActionResult` のレスポンスパターンを組み立てる。
5. 生成したアクション行を `_render_controller_from_actions` に渡し、完全なクラスを返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: `GET/POST` ルートが設定される。
  - **Expected Output**: `HttpGet/HttpPost` のアクションが生成される。
- **Edge Cases**:
  - **Scenario**: `DELETE /items/{id}` を含む。
  - **Expected Output / Behavior**: `id` 引数付き Delete アクションが生成される。

## 3. Dependencies
- **Internal**: なし
