# OrdersProject

## Purpose

ASP.NET Core Web API のサンプルとして、Repository パターンを使った Orders / Inventory の CRUD 雛形を生成する。

## Project Spec

### Tech
- **Language**: C#
- **Framework**: ASP.NET Core Web API
- **Target**: .NET 10

### Architecture
- **Style**: Layered (Controller -> Service -> Repository)
- **DI**: Built-in ASP.NET Core DI

### Data Access
- **Provider**: SqlServer
- **Strategy**: Dapper

### Modules
- **Controller**: OrdersController
  - routes:
  - GET /orders
  - GET /orders/{id}
  - POST /orders
  - PUT /orders/{id}
  - DELETE /orders/{id}
- **Controller**: InventoryController
  - routes:
  - GET /inventory
  - GET /inventory/{id}
  - POST /inventory
  - PUT /inventory/{id}
  - DELETE /inventory/{id}
- **Service**: OrderService
  - methods:
  - GetOrders(): List<OrderResponse>
  - GetOrderById(id:int): OrderResponse?
  - CreateOrder(req:OrderCreateRequest): OrderResponse?
  - UpdateOrder(id:int, req:OrderCreateRequest): OrderResponse?
  - DeleteOrder(id:int): bool
- **Service**: InventoryService
  - methods:
  - GetInventoryItems(): List<InventoryResponse>
  - GetInventoryItemById(id:int): InventoryResponse?
  - CreateInventoryItem(req:InventoryCreateRequest): InventoryResponse?
  - UpdateInventoryItem(id:int, req:InventoryCreateRequest): InventoryResponse?
  - DeleteInventoryItem(id:int): bool
- **Repository**: OrderRepository
  - methods:
  - FetchAll(): List<Order>
  - FetchById(id:int): Order?
  - Insert(order:Order): Order
  - Update(id:int, order:Order): Order?
  - Delete(id:int): bool
- **Repository**: InventoryRepository
  - methods:
  - FetchAll(): List<InventoryItem>
  - FetchById(id:int): InventoryItem?
  - Insert(item:InventoryItem): InventoryItem
  - Update(id:int, item:InventoryItem): InventoryItem?
  - Delete(id:int): bool

### Entities / DTO
- **Entity**: Order
  - Id:int
  - CustomerName:string
  - TotalAmount:decimal
  - CreatedAt:datetime
- **Entity**: InventoryItem
  - Id:int
  - Sku:string
  - Quantity:int
  - UpdatedAt:datetime
- **DTO**: OrderCreateRequest
  - CustomerName:string
  - TotalAmount:decimal
- **DTO**: OrderResponse
  - Id:int
  - CustomerName:string
  - TotalAmount:decimal
  - CreatedAt:datetime
- **DTO**: InventoryCreateRequest
  - Sku:string
  - Quantity:int
- **DTO**: InventoryResponse
  - Id:int
  - Sku:string
  - Quantity:int
  - UpdatedAt:datetime

### Infrastructure
- **Logging**: Console
- **Configuration**: appsettings.json

### Validation
- **OrderCreateRequest.CustomerName**: required, max_len=100
- **OrderCreateRequest.TotalAmount**: required, min_value=0
- **InventoryCreateRequest.Sku**: required, min_len=3, max_len=50
- **InventoryCreateRequest.Quantity**: required, min_value=0, max_value=100000

## Method Specs

### OrderService.GetOrders
- **Input**: none
- **Output**: `List<OrderResponse>` (empty list if none)
- **Steps**:
  - op:service.list
- **Core Logic**:
  1. Repository から全件取得する。
  2. 取得結果を `OrderResponse` に変換する。
  3. 変換結果を返す（空なら空配列）。
- **Test Cases**:
  - {"id":"tc_order_list_two","name":"TwoItems_ReturnsTwo","method":"GetOrders","arrange":["var repo = new FakeRepo();","repo.Items.Add(new Order { Id = 1, CustomerName = \"Alpha\", TotalAmount = 10m, CreatedAt = DateTime.UtcNow });","repo.Items.Add(new Order { Id = 2, CustomerName = \"Beta\", TotalAmount = 20m, CreatedAt = DateTime.UtcNow });","var service = new OrderService(repo);"],"act":"var result = service.GetOrders();","assert":["Assert.Equal(2, result.Count);","Assert.Equal(\"Alpha\", result[0].CustomerName);"]}

### OrderService.GetOrderById
- **Input**: `id:int`
- **Output**: `OrderResponse` or `null`
- **Steps**:
  - op:service.get
- **Core Logic**:
  1. Repository から id で取得する。
  2. 取得結果を `OrderResponse` に変換する。
  3. 取得できない場合は null を返す。
- **Test Cases**:
  - {"id":"tc_order_get_exists","name":"Exists_ReturnsResponse","method":"GetOrderById","arrange":["var repo = new FakeRepo();","repo.Items.Add(new Order { Id = 1, CustomerName = \"Alpha\", TotalAmount = 10m, CreatedAt = DateTime.UtcNow });","var service = new OrderService(repo);"],"act":"var result = service.GetOrderById(1);","assert":["Assert.NotNull(result);","Assert.Equal(1, result!.Id);"]}
  - {"id":"tc_order_get_missing","name":"Missing_ReturnsNull","method":"GetOrderById","arrange":["var repo = new FakeRepo();","var service = new OrderService(repo);"],"act":"var result = service.GetOrderById(99);","assert":["Assert.Null(result);"]}

### OrderService.CreateOrder
- **Input**: `OrderCreateRequest`
- **Output**: `OrderResponse` or `null`
- **Steps**:
  - op:service.create
- **Core Logic**:
  1. 入力が null の場合は null を返す。
  2. CustomerName が空または長さ > 100 の場合は null を返す。
  3. TotalAmount が 0 未満の場合は null を返す。
  4. [ops:to_entity] 入力DTOを Order に変換する。
  5. [ops:repo_insert] Repository に保存して結果を受け取る。
  6. [ops:to_response] 保存結果を `OrderResponse` に変換して返す。
- **Test Cases**:
  - {"id":"tc_order_create_valid","name":"Valid_ReturnsResponse","method":"CreateOrder","arrange":["var repo = new FakeRepo();","var service = new OrderService(repo);","var req = new OrderCreateRequest { CustomerName = \"Alpha\", TotalAmount = 10m };"],"act":"var result = service.CreateOrder(req);","assert":["Assert.NotNull(result);","Assert.Equal(\"Alpha\", result!.CustomerName);"]}
  - {"id":"tc_order_create_invalid","name":"InvalidAmount_ReturnsNull","method":"CreateOrder","arrange":["var repo = new FakeRepo();","var service = new OrderService(repo);","var req = new OrderCreateRequest { CustomerName = \"Alpha\", TotalAmount = -1m };"],"act":"var result = service.CreateOrder(req);","assert":["Assert.Null(result);"]}

### OrderService.UpdateOrder
- **Input**: `id:int`, `OrderCreateRequest`
- **Output**: `OrderResponse` or `null`
- **Steps**:
  - op:service.update
- **Core Logic**:
  1. 入力が null の場合は null を返す。
  2. CustomerName が空または長さ > 100 の場合は null を返す。
  3. TotalAmount が 0 未満の場合は null を返す。
  4. Repository から対象注文を取得する。存在しない場合は null を返す。
  5. [ops:update_fields] 取得した Order に CustomerName / TotalAmount を反映する。
  6. [ops:repo_update] Repository で更新し、結果を `OrderResponse` に変換して返す。
- **Test Cases**:
  - {"id":"tc_order_update_valid","name":"Valid_UpdatesFields","method":"UpdateOrder","arrange":["var repo = new FakeRepo();","repo.Items.Add(new Order { Id = 1, CustomerName = \"Old\", TotalAmount = 5m, CreatedAt = DateTime.UtcNow });","var service = new OrderService(repo);","var req = new OrderCreateRequest { CustomerName = \"New\", TotalAmount = 20m };"],"act":"var result = service.UpdateOrder(1, req);","assert":["Assert.NotNull(result);","Assert.Equal(\"New\", result!.CustomerName);"]}
  - {"id":"tc_order_update_missing","name":"Missing_ReturnsNull","method":"UpdateOrder","arrange":["var repo = new FakeRepo();","var service = new OrderService(repo);","var req = new OrderCreateRequest { CustomerName = \"New\", TotalAmount = 20m };"],"act":"var result = service.UpdateOrder(1, req);","assert":["Assert.Null(result);"]}

### OrderService.DeleteOrder
- **Input**: `id:int`
- **Output**: `bool`
- **Steps**:
  - op:service.delete
- **Core Logic**:
  1. Repository で削除を実行する。
  2. 成功なら true、失敗なら false を返す。
- **Test Cases**:
  - {"id":"tc_order_delete_true","name":"DeleteTrue_ReturnsTrue","method":"DeleteOrder","arrange":["var repo = new FakeRepo { DeleteResult = true };","var service = new OrderService(repo);"],"act":"var result = service.DeleteOrder(1);","assert":["Assert.True(result);"]}
  - {"id":"tc_order_delete_false","name":"DeleteFalse_ReturnsFalse","method":"DeleteOrder","arrange":["var repo = new FakeRepo { DeleteResult = false };","var service = new OrderService(repo);"],"act":"var result = service.DeleteOrder(1);","assert":["Assert.False(result);"]}

### OrderRepository.FetchAll
- **Input**: none
- **Output**: `List<Order>` (empty list if none)
- **Steps**:
  - op:repo.fetch_all
- **Core Logic**:
  1. `SELECT Id, CustomerName, TotalAmount, CreatedAt FROM Orders` を実行する。
  2. 結果を `Order` のリストで返す。
- **Test Cases**:
  - Happy Path: 2件返る場合、2件の Order を返す。
  - Edge Case: 0件の場合は空リストを返す。

### OrderRepository.FetchById
- **Input**: `id:int`
- **Output**: `Order` or `null`
- **Steps**:
  - op:repo.fetch_by_id
- **Core Logic**:
  1. `SELECT Id, CustomerName, TotalAmount, CreatedAt FROM Orders WHERE Id = @Id` を実行する。
  2. 取得できない場合は null。
- **Test Cases**:
  - Happy Path: 存在する場合、Order を返す。
  - Edge Case: 存在しない場合は null を返す。

### OrderRepository.Insert
- **Input**: `Order`
- **Output**: `Order`
- **Steps**:
  - op:repo.insert
- **Core Logic**:
  1. `INSERT INTO Orders (CustomerName, TotalAmount, CreatedAt) VALUES (@CustomerName, @TotalAmount, @CreatedAt)` を実行する。
  2. 実行結果の Id を反映した Order を返す。
- **Test Cases**:
  - Happy Path: Insert 成功時、Id を含んだ Order を返す。

### OrderRepository.Update
- **Input**: `id:int`, `Order`
- **Output**: `Order` or `null`
- **Steps**:
  - op:repo.update
- **Core Logic**:
  1. `UPDATE Orders SET CustomerName=@CustomerName, TotalAmount=@TotalAmount WHERE Id=@Id` を実行する。
  2. 更新件数が0なら null。
  3. 更新成功なら Id を反映した Order を返す。
- **Test Cases**:
  - Happy Path: 更新成功時、更新された Order を返す。
  - Edge Case: 対象が存在しない場合は null を返す。

### OrderRepository.Delete
- **Input**: `id:int`
- **Output**: `bool`
- **Steps**:
  - op:repo.delete
- **Core Logic**:
  1. `DELETE FROM Orders WHERE Id=@Id` を実行する。
  2. 影響件数が1以上なら true、0なら false。
- **Test Cases**:
  - Happy Path: 削除成功時 true。
  - Edge Case: 対象が存在しない場合は false。

### InventoryService.GetInventoryItems
- **Input**: none
- **Output**: `List<InventoryResponse>` (empty list if none)
- **Steps**:
  - op:service.list
- **Core Logic**:
  1. Repository から全件取得する。
  2. 取得結果を `InventoryResponse` に変換する。
  3. 変換結果を返す（空なら空配列）。
- **Test Cases**:
  - {"id":"tc_inventory_list_two","name":"TwoItems_ReturnsTwo","method":"GetInventoryItems","arrange":["var repo = new FakeRepo();","repo.Items.Add(new InventoryItem { Id = 1, Sku = \"SKU-1\", Quantity = 10, UpdatedAt = DateTime.UtcNow });","repo.Items.Add(new InventoryItem { Id = 2, Sku = \"SKU-2\", Quantity = 5, UpdatedAt = DateTime.UtcNow });","var service = new InventoryService(repo);"],"act":"var result = service.GetInventoryItems();","assert":["Assert.Equal(2, result.Count);","Assert.Equal(\"SKU-1\", result[0].Sku);"]}

### InventoryService.GetInventoryItemById
- **Input**: `id:int`
- **Output**: `InventoryResponse` or `null`
- **Steps**:
  - op:service.get
- **Core Logic**:
  1. Repository から id で取得する。
  2. 取得結果を `InventoryResponse` に変換する。
  3. 取得できない場合は null を返す。
- **Test Cases**:
  - {"id":"tc_inventory_get_exists","name":"Exists_ReturnsResponse","method":"GetInventoryItemById","arrange":["var repo = new FakeRepo();","repo.Items.Add(new InventoryItem { Id = 1, Sku = \"SKU-1\", Quantity = 10, UpdatedAt = DateTime.UtcNow });","var service = new InventoryService(repo);"],"act":"var result = service.GetInventoryItemById(1);","assert":["Assert.NotNull(result);","Assert.Equal(1, result!.Id);"]}
  - {"id":"tc_inventory_get_missing","name":"Missing_ReturnsNull","method":"GetInventoryItemById","arrange":["var repo = new FakeRepo();","var service = new InventoryService(repo);"],"act":"var result = service.GetInventoryItemById(99);","assert":["Assert.Null(result);"]}

### InventoryService.CreateInventoryItem
- **Input**: `InventoryCreateRequest`
- **Output**: `InventoryResponse` or `null`
- **Steps**:
  - op:service.create
- **Core Logic**:
  1. 入力が null の場合は null を返す。
  2. Sku が空または長さ < 3 または長さ > 50 の場合は null を返す。
  3. Quantity が 0 未満の場合は null を返す。
  4. [ops:to_entity] 入力DTOを InventoryItem に変換する。
  5. [ops:repo_insert] Repository に保存して結果を受け取る。
  6. [ops:to_response] 保存結果を `InventoryResponse` に変換して返す。
- **Test Cases**:
  - {"id":"tc_inventory_create_valid","name":"Valid_ReturnsResponse","method":"CreateInventoryItem","arrange":["var repo = new FakeRepo();","var service = new InventoryService(repo);","var req = new InventoryCreateRequest { Sku = \"SKU-1\", Quantity = 10 };"],"act":"var result = service.CreateInventoryItem(req);","assert":["Assert.NotNull(result);","Assert.Equal(\"SKU-1\", result!.Sku);"]}
  - {"id":"tc_inventory_create_invalid","name":"InvalidQuantity_ReturnsNull","method":"CreateInventoryItem","arrange":["var repo = new FakeRepo();","var service = new InventoryService(repo);","var req = new InventoryCreateRequest { Sku = \"SKU-1\", Quantity = -1 };"],"act":"var result = service.CreateInventoryItem(req);","assert":["Assert.Null(result);"]}

### InventoryService.UpdateInventoryItem
- **Input**: `id:int`, `InventoryCreateRequest`
- **Output**: `InventoryResponse` or `null`
- **Steps**:
  - op:service.update
- **Core Logic**:
  1. 入力が null の場合は null を返す。
  2. Sku が空または長さ < 3 または長さ > 50 の場合は null を返す。
  3. Quantity が 0 未満の場合は null を返す。
  4. Repository から対象在庫を取得する。存在しない場合は null を返す。
  5. [ops:update_fields] 取得した InventoryItem に Sku / Quantity を反映する。
  6. [ops:repo_update] Repository で更新し、結果を `InventoryResponse` に変換して返す。
- **Test Cases**:
  - {"id":"tc_inventory_update_valid","name":"Valid_UpdatesFields","method":"UpdateInventoryItem","arrange":["var repo = new FakeRepo();","repo.Items.Add(new InventoryItem { Id = 1, Sku = \"SKU-OLD\", Quantity = 1, UpdatedAt = DateTime.UtcNow });","var service = new InventoryService(repo);","var req = new InventoryCreateRequest { Sku = \"SKU-NEW\", Quantity = 10 };"],"act":"var result = service.UpdateInventoryItem(1, req);","assert":["Assert.NotNull(result);","Assert.Equal(\"SKU-NEW\", result!.Sku);"]}
  - {"id":"tc_inventory_update_missing","name":"Missing_ReturnsNull","method":"UpdateInventoryItem","arrange":["var repo = new FakeRepo();","var service = new InventoryService(repo);","var req = new InventoryCreateRequest { Sku = \"SKU-NEW\", Quantity = 10 };"],"act":"var result = service.UpdateInventoryItem(1, req);","assert":["Assert.Null(result);"]}

### InventoryService.DeleteInventoryItem
- **Input**: `id:int`
- **Output**: `bool`
- **Steps**:
  - op:service.delete
- **Core Logic**:
  1. Repository で削除を実行する。
  2. 成功なら true、失敗なら false を返す。
- **Test Cases**:
  - {"id":"tc_inventory_delete_true","name":"DeleteTrue_ReturnsTrue","method":"DeleteInventoryItem","arrange":["var repo = new FakeRepo { DeleteResult = true };","var service = new InventoryService(repo);"],"act":"var result = service.DeleteInventoryItem(1);","assert":["Assert.True(result);"]}
  - {"id":"tc_inventory_delete_false","name":"DeleteFalse_ReturnsFalse","method":"DeleteInventoryItem","arrange":["var repo = new FakeRepo { DeleteResult = false };","var service = new InventoryService(repo);"],"act":"var result = service.DeleteInventoryItem(1);","assert":["Assert.False(result);"]}

### InventoryRepository.FetchAll
- **Input**: none
- **Output**: `List<InventoryItem>` (empty list if none)
- **Steps**:
  - op:repo.fetch_all
- **Core Logic**:
  1. `SELECT Id, Sku, Quantity, UpdatedAt FROM Inventory` を実行する。
  2. 結果を `InventoryItem` のリストで返す。
- **Test Cases**:
  - Happy Path: 2件返る場合、2件の InventoryItem を返す。
  - Edge Case: 0件の場合は空リストを返す。

### InventoryRepository.FetchById
- **Input**: `id:int`
- **Output**: `InventoryItem` or `null`
- **Steps**:
  - op:repo.fetch_by_id
- **Core Logic**:
  1. `SELECT Id, Sku, Quantity, UpdatedAt FROM Inventory WHERE Id = @Id` を実行する。
  2. 取得できない場合は null。
- **Test Cases**:
  - Happy Path: 存在する場合、InventoryItem を返す。
  - Edge Case: 存在しない場合は null を返す。

### InventoryRepository.Insert
- **Input**: `InventoryItem`
- **Output**: `InventoryItem`
- **Steps**:
  - op:repo.insert
- **Core Logic**:
  1. `INSERT INTO Inventory (Sku, Quantity, UpdatedAt) VALUES (@Sku, @Quantity, @UpdatedAt)` を実行する。
  2. 実行結果の Id を反映した InventoryItem を返す。
- **Test Cases**:
  - Happy Path: Insert 成功時、Id を含んだ InventoryItem を返す。

### InventoryRepository.Update
- **Input**: `id:int`, `InventoryItem`
- **Output**: `InventoryItem` or `null`
- **Steps**:
  - op:repo.update
- **Core Logic**:
  1. `UPDATE Inventory SET Sku=@Sku, Quantity=@Quantity WHERE Id=@Id` を実行する。
  2. 更新件数が0なら null。
  3. 更新成功なら Id を反映した InventoryItem を返す。
- **Test Cases**:
  - Happy Path: 更新成功時、更新された InventoryItem を返す。
  - Edge Case: 対象が存在しない場合は null を返す。

### InventoryRepository.Delete
- **Input**: `id:int`
- **Output**: `bool`
- **Steps**:
  - op:repo.delete
- **Core Logic**:
  1. `DELETE FROM Inventory WHERE Id=@Id` を実行する。
  2. 影響件数が1以上なら true、0なら false。
- **Test Cases**:
  - Happy Path: 削除成功時 true。
  - Edge Case: 対象が存在しない場合は false。

## Generation Hints (Reusable)

### Entities
- **Primary Entity**: Order
- **Primary Key**: Id:int
- **Entity Plural**: Orders
- **Create Request DTO**: OrderCreateRequest
- **Response DTO**: OrderResponse

### DTO Mapping
  - **CreateRequest -> Entity**:
    - CustomerName -> CustomerName
    - TotalAmount -> TotalAmount
    - UtcNow -> CreatedAt
- **Entity -> Response**:
  - Id -> Id
  - CustomerName -> CustomerName
  - TotalAmount -> TotalAmount
  - CreatedAt -> CreatedAt

### CRUD Method Template
- **List**:
  - Service: Get{EntityPlural}
  - Repository: FetchAll
  - Route: GET /{entityPlural}
- **GetById**:
  - Service: Get{Entity}ById
  - Repository: FetchById
  - Route: GET /{entityPlural}/{id}
- **Create**:
  - Service: Create{Entity}
  - Repository: Insert
  - Route: POST /{entityPlural}
- **Update**:
  - Service: Update{Entity}
  - Repository: Update
  - Route: PUT /{entityPlural}/{id}
- **Delete**:
  - Service: Delete{Entity}
  - Repository: Delete
  - Route: DELETE /{entityPlural}/{id}

### SQL Template
- **SelectAll**: `SELECT {columns} FROM {table}`
- **SelectById**: `SELECT {columns} FROM {table} WHERE {pk} = @Id`
- **Insert**: `INSERT INTO {table} ({columnsNoPk}) VALUES ({paramsNoPk})`
- **Update**: `UPDATE {table} SET {assignmentsNoPk} WHERE {pk} = @Id`
- **Delete**: `DELETE FROM {table} WHERE {pk} = @Id`

### Validation Template
- **Required String**: not empty
- **Max Length**: use explicit length per field
- **Format**: allow per-field rules (e.g., email must contain `@`)

### Entity Specs
- **Entity**: Order
  - Plural: Orders
  - Create DTO: OrderCreateRequest
  - Response DTO: OrderResponse
  - Controller: OrdersController
  - Service: OrderService
  - Repository: OrderRepository
  - Routes:
    - GET /orders
    - GET /orders/{id}
    - POST /orders
    - PUT /orders/{id}
    - DELETE /orders/{id}
  - Create Mapping:
    - CustomerName -> CustomerName
    - TotalAmount -> TotalAmount
    - UtcNow -> CreatedAt
  - Response Mapping:
    - Id -> Id
    - CustomerName -> CustomerName
    - TotalAmount -> TotalAmount
    - CreatedAt -> CreatedAt
- **Entity**: InventoryItem
  - Plural: Inventory
  - Create DTO: InventoryCreateRequest
  - Response DTO: InventoryResponse
  - Controller: InventoryController
  - Service: InventoryService
  - Repository: InventoryRepository
  - Routes:
    - GET /inventory
    - GET /inventory/{id}
    - POST /inventory
    - PUT /inventory/{id}
    - DELETE /inventory/{id}
  - Create Mapping:
    - Sku -> Sku
    - Quantity -> Quantity
    - UtcNow -> UpdatedAt
  - Response Mapping:
    - Id -> Id
    - Sku -> Sku
    - Quantity -> Quantity
    - UpdatedAt -> UpdatedAt
