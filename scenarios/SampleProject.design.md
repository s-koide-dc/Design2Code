# SampleProject

## Purpose

ASP.NET Core Web API のサンプルとして、Repository パターンを使った Users CRUD の雛形を生成する。

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
- **Controller**: UsersController
  - routes:
  - GET /users
  - GET /users/{id}
  - POST /users
  - PUT /users/{id}
  - DELETE /users/{id}
- **Controller**: ProductsController
  - routes:
  - GET /products
  - GET /products/{id}
  - POST /products
  - PUT /products/{id}
  - DELETE /products/{id}
- **Service**: UserService
  - methods:
  - GetUsers(): List<UserResponse>
  - GetUserById(id:int): UserResponse?
  - CreateUser(req:UserCreateRequest): UserResponse?
  - UpdateUser(id:int, req:UserCreateRequest): UserResponse?
  - DeleteUser(id:int): bool
- **Service**: ProductService
  - methods:
  - GetProducts(): List<ProductResponse>
  - GetProductById(id:int): ProductResponse?
  - CreateProduct(req:ProductCreateRequest): ProductResponse?
  - UpdateProduct(id:int, req:ProductCreateRequest): ProductResponse?
  - DeleteProduct(id:int): bool
- **Repository**: UserRepository
  - methods:
  - FetchAll(): List<User>
  - FetchById(id:int): User?
  - Insert(user:User): User
  - Update(id:int, user:User): User?
  - Delete(id:int): bool
- **Repository**: ProductRepository
  - methods:
  - FetchAll(): List<Product>
  - FetchById(id:int): Product?
  - Insert(user:Product): Product
  - Update(id:int, user:Product): Product?
  - Delete(id:int): bool

### Entities / DTO
- **Entity**: User
  - Id:int
  - Name:string
  - Email:string
  - CreatedAt:datetime
- **Entity**: Product
  - Id:int
  - Name:string
  - Price:decimal
  - CreatedAt:datetime
- **DTO**: UserCreateRequest
  - Name:string
  - Email:string
- **DTO**: UserResponse
  - Id:int
  - Name:string
  - Email:string
  - CreatedAt:datetime
- **DTO**: ProductCreateRequest
  - Name:string
  - Price:decimal
- **DTO**: ProductResponse
  - Id:int
  - Name:string
  - Price:decimal
  - CreatedAt:datetime

### Infrastructure
- **Logging**: Console
- **Configuration**: appsettings.json

### Validation
- **UserCreateRequest.Name**: required, max_len=100
- **UserCreateRequest.Email**: required, contains=@
- **ProductCreateRequest.Name**: required, min_len=2, max_len=100
- **ProductCreateRequest.Price**: required, min_value=0, max_value=100000

## Method Specs

### UserService.GetUsers
- **Input**: none
- **Output**: List<UserResponse> (empty list if none)
- **Steps**:
  - op:service.list
- **Core Logic**:
  1. [ACTION|FETCH|User|List<User>|NONE] Repository から全件取得する。
  2. [ACTION|TRANSFORM|UserResponse|List<UserResponse>|NONE] 取得結果を UserResponse に変換する。
  3. [ACTION|RETURN|UserResponse|List<UserResponse>|NONE] 変換結果を返す（空なら空配列）。
- **Test Cases**:
  - {"id":"tc_user_list_two","name":"TwoItems_ReturnsTwo","method":"GetUsers","arrange":["var repo = new FakeRepo();","repo.Items.Add(new User { Id = 1, Name = \"Alice\", Email = \"alice@example.com\", CreatedAt = DateTime.UtcNow });","repo.Items.Add(new User { Id = 2, Name = \"Bob\", Email = \"bob@example.com\", CreatedAt = DateTime.UtcNow });","var service = new UserService(repo);"],"act":"var result = service.GetUsers();","assert":["Assert.Equal(2, result.Count);","Assert.Equal(\"Alice\", result[0].Name);"]}

### UserService.GetUserById
- **Input**: id:int
- **Output**: UserResponse or null
- **Steps**:
  - op:service.get
- **Core Logic**:
1. [ACTION|FETCH|User|User?|NONE] Repository から id で単一の対象を取得する。
  2. [ACTION|TRANSFORM|UserResponse|UserResponse?|NONE] 取得結果を UserResponse に変換する。
  3. [ACTION|RETURN|UserResponse|UserResponse?|NONE] 取得できない場合は null を返す。
- **Test Cases**:
  - {"id":"tc_user_get_exists","name":"Exists_ReturnsResponse","method":"GetUserById","arrange":["var repo = new FakeRepo();","repo.Items.Add(new User { Id = 1, Name = \"Alice\", Email = \"alice@example.com\", CreatedAt = DateTime.UtcNow });","var service = new UserService(repo);"],"act":"var result = service.GetUserById(1);","assert":["Assert.NotNull(result);","Assert.Equal(1, result!.Id);"]}
  - {"id":"tc_user_get_missing","name":"Missing_ReturnsNull","method":"GetUserById","arrange":["var repo = new FakeRepo();","var service = new UserService(repo);"],"act":"var result = service.GetUserById(99);","assert":["Assert.Null(result);"]}

### UserService.CreateUser
- **Input**: UserCreateRequest
- **Output**: UserResponse or null
- **Steps**:
  - op:service.create
- **Core Logic**:
  1. [ACTION|VALIDATE|UserCreateRequest|bool|NONE] 入力が null の場合は null を返す。
  2. [ACTION|VALIDATE|UserCreateRequest|bool|NONE] Name が空または長さ > 100 の場合は null を返す。 [numeric:eq:100]
  3. [ACTION|VALIDATE|UserCreateRequest|bool|NONE] Email が空または @ を含まない場合は null を返す。
  4. [ACTION|TRANSFORM|User|User|NONE] 入力DTOを User に変換する。
  5. [ACTION|PERSIST|User|User|DB] Repository に保存して結果を受け取る。
  6. [ACTION|RETURN|UserResponse|UserResponse?|NONE] 保存結果を UserResponse に変換して返す。
- **Test Cases**:
  - {"id":"tc_user_create_valid","name":"Valid_ReturnsResponse","method":"CreateUser","arrange":["var repo = new FakeRepo();","var service = new UserService(repo);","var req = new UserCreateRequest { Name = \"Alice\", Email = \"alice@example.com\" };"],"act":"var result = service.CreateUser(req);","assert":["Assert.NotNull(result);","Assert.Equal(\"Alice\", result!.Name);"]}
  - {"id":"tc_user_create_invalid","name":"InvalidEmail_ReturnsNull","method":"CreateUser","arrange":["var repo = new FakeRepo();","var service = new UserService(repo);","var req = new UserCreateRequest { Name = \"Alice\", Email = \"invalid\" };"],"act":"var result = service.CreateUser(req);","assert":["Assert.Null(result);"]}

### UserService.UpdateUser
- **Input**: id:int, UserCreateRequest
- **Output**: UserResponse or null
- **Steps**:
  - op:service.update
- **Core Logic**:
  1. [ACTION|VALIDATE|UserCreateRequest|bool|NONE] 入力が null の場合は null を返す。
  2. [ACTION|VALIDATE|UserCreateRequest|bool|NONE] Name が空または長さ > 100 の場合は null を返す。 [numeric:eq:100]
  3. [ACTION|VALIDATE|UserCreateRequest|bool|NONE] Email が空または @ を含まない場合は null を返す。
  4. [ACTION|FETCH|User|User?|NONE] Repository から対象ユーザーを取得する。存在しない場合は null を返す。
  5. [ACTION|TRANSFORM|User|User|NONE] 取得した User に Name/Email を反映する。
  6. [ACTION|PERSIST|User|UserResponse?|DB] Repository で更新し、結果を UserResponse に変換して返す。
- **Test Cases**:
  - {"id":"tc_user_update_valid","name":"Valid_UpdatesFields","method":"UpdateUser","arrange":["var repo = new FakeRepo();","repo.Items.Add(new User { Id = 1, Name = \"Old\", Email = \"old@example.com\", CreatedAt = DateTime.UtcNow });","var service = new UserService(repo);","var req = new UserCreateRequest { Name = \"New\", Email = \"new@example.com\" };"],"act":"var result = service.UpdateUser(1, req);","assert":["Assert.NotNull(result);","Assert.Equal(\"New\", result!.Name);"]}
  - {"id":"tc_user_update_missing","name":"Missing_ReturnsNull","method":"UpdateUser","arrange":["var repo = new FakeRepo();","var service = new UserService(repo);","var req = new UserCreateRequest { Name = \"New\", Email = \"new@example.com\" };"],"act":"var result = service.UpdateUser(1, req);","assert":["Assert.Null(result);"]}

### UserService.DeleteUser
- **Input**: id:int
- **Output**: bool
- **Steps**:
  - op:service.delete
- **Core Logic**:
  1. [ACTION|PERSIST|User|bool|DB] Repository で削除を実行する。
  2. [ACTION|RETURN|User|bool|NONE] 成功なら true、失敗なら false を返す。
- **Test Cases**:
  - {"id":"tc_user_delete_true","name":"DeleteTrue_ReturnsTrue","method":"DeleteUser","arrange":["var repo = new FakeRepo { DeleteResult = true };","var service = new UserService(repo);"],"act":"var result = service.DeleteUser(1);","assert":["Assert.True(result);"]}
  - {"id":"tc_user_delete_false","name":"DeleteFalse_ReturnsFalse","method":"DeleteUser","arrange":["var repo = new FakeRepo { DeleteResult = false };","var service = new UserService(repo);"],"act":"var result = service.DeleteUser(1);","assert":["Assert.False(result);"]}

### UserRepository.FetchAll
- **Input**: none
- **Output**: List<User> (empty list if none)
- **Steps**:
  - op:repo.fetch_all
- **Core Logic**:
- [data_source|users_db|db] users_db data source
  1. [ACTION|DATABASE_QUERY|User|List<User>|DB|users_db|db] [semantic_roles:{"sql":"SELECT Id, Name, Email, CreatedAt FROM Users"}] SELECT Id, Name, Email, CreatedAt FROM Users を実行する。
  2. [ACTION|RETURN|User|List<User>|NONE] 結果を User のリストで返す。
- **Test Cases**:
  - Happy Path: 2件返る場合、2件の User を返す。
  - Edge Case: 0件の場合は空リストを返す。

### UserRepository.FetchById
- **Input**: id:int
- **Output**: User or null
- **Steps**:
  - op:repo.fetch_by_id
- **Core Logic**:
- [data_source|users_db|db] users_db data source
  1. [ACTION|DATABASE_QUERY|User|User?|DB|users_db|db] [semantic_roles:{"sql":"SELECT Id, Name, Email, CreatedAt FROM Users WHERE Id = @Id"}] SELECT Id, Name, Email, CreatedAt FROM Users WHERE Id = @Id を実行する。
  2. [ACTION|RETURN|User|User?|NONE] 取得できない場合は null。
- **Test Cases**:
  - Happy Path: 存在する場合、User を返す。
  - Edge Case: 存在しない場合は null を返す。

### UserRepository.Insert
- **Input**: User
- **Output**: User
- **Steps**:
  - op:repo.insert
- **Core Logic**:
- [data_source|users_db|db] users_db data source
  1. [ACTION|PERSIST|User|User|DB|users_db|db] [semantic_roles:{"sql":"INSERT INTO Users (Name, Email, CreatedAt) VALUES (@Name, @Email, @CreatedAt)"}] INSERT INTO Users (Name, Email, CreatedAt) VALUES (@Name, @Email, @CreatedAt) を実行する。
  2. [ACTION|RETURN|User|User|NONE] 実行結果の Id を反映した User を返す。
- **Test Cases**:
  - Happy Path: Insert 成功時、Id を含んだ User を返す。

### UserRepository.Update
- **Input**: id:int, User
- **Output**: User or null
- **Steps**:
  - op:repo.update
- **Core Logic**:
- [data_source|users_db|db] users_db data source
  1. [ACTION|PERSIST|User|User?|DB|users_db|db] [semantic_roles:{"sql":"UPDATE Users SET Name=@Name, Email=@Email WHERE Id=@Id"}] UPDATE Users SET Name=@Name, Email=@Email WHERE Id=@Id を実行する。
  2. [ACTION|RETURN|User|User?|NONE] 更新件数が0なら null。 [numeric:eq:0]
  3. [ACTION|RETURN|User|User?|NONE] 更新成功なら Id を反映した User を返す。
- **Test Cases**:
  - Happy Path: 更新成功時、更新された User を返す。
  - Edge Case: 対象が存在しない場合は null を返す。

### UserRepository.Delete
- **Input**: id:int
- **Output**: bool
- **Steps**:
  - op:repo.delete
- **Core Logic**:
- [data_source|users_db|db] users_db data source
  1. [ACTION|PERSIST|User|bool|DB|users_db|db] [semantic_roles:{"sql":"DELETE FROM Users WHERE Id=@Id"}] DELETE FROM Users WHERE Id=@Id を実行する。
  2. [ACTION|RETURN|User|bool|NONE] 影響件数が1以上なら true、0なら false。 [numeric:ge:1] [numeric:eq:0]
- **Test Cases**:
  - Happy Path: 削除成功時 true。
  - Edge Case: 対象が存在しない場合は false。

### ProductService.GetProducts
- **Input**: none
- **Output**: List<ProductResponse> (empty list if none)
- **Steps**:
  - op:service.list
- **Core Logic**:
  1. [ACTION|FETCH|Product|List<Product>|NONE] Repository から全件取得する。
  2. [ACTION|TRANSFORM|ProductResponse|List<ProductResponse>|NONE] 取得結果を ProductResponse に変換する。
  3. [ACTION|RETURN|ProductResponse|List<ProductResponse>|NONE] 変換結果を返す（空なら空配列）。
- **Test Cases**:
  - {"id":"tc_product_list_two","name":"TwoItems_ReturnsTwo","method":"GetProducts","arrange":["var repo = new FakeRepo();","repo.Items.Add(new Product { Id = 1, Name = \"ItemA\", Price = 10m, CreatedAt = DateTime.UtcNow });","repo.Items.Add(new Product { Id = 2, Name = \"ItemB\", Price = 20m, CreatedAt = DateTime.UtcNow });","var service = new ProductService(repo);"],"act":"var result = service.GetProducts();","assert":["Assert.Equal(2, result.Count);","Assert.Equal(\"ItemA\", result[0].Name);"]}

### ProductService.GetProductById
- **Input**: id:int
- **Output**: ProductResponse or null
- **Steps**:
  - op:service.get
- **Core Logic**:
1. [ACTION|FETCH|Product|Product?|NONE] Repository から id で単一の対象を取得する。
  2. [ACTION|TRANSFORM|ProductResponse|ProductResponse?|NONE] 取得結果を ProductResponse に変換する。
  3. [ACTION|RETURN|ProductResponse|ProductResponse?|NONE] 取得できない場合は null を返す。
- **Test Cases**:
  - {"id":"tc_product_get_exists","name":"Exists_ReturnsResponse","method":"GetProductById","arrange":["var repo = new FakeRepo();","repo.Items.Add(new Product { Id = 1, Name = \"ItemA\", Price = 10m, CreatedAt = DateTime.UtcNow });","var service = new ProductService(repo);"],"act":"var result = service.GetProductById(1);","assert":["Assert.NotNull(result);","Assert.Equal(1, result!.Id);"]}
  - {"id":"tc_product_get_missing","name":"Missing_ReturnsNull","method":"GetProductById","arrange":["var repo = new FakeRepo();","var service = new ProductService(repo);"],"act":"var result = service.GetProductById(99);","assert":["Assert.Null(result);"]}

### ProductService.CreateProduct
- **Input**: ProductCreateRequest
- **Output**: ProductResponse or null
- **Steps**:
  - op:service.create
- **Core Logic**:
  1. [ACTION|VALIDATE|ProductCreateRequest|bool|NONE] 入力が null の場合は null を返す。
  2. [ACTION|VALIDATE|ProductCreateRequest|bool|NONE] Name が空または長さ > 100 の場合は null を返す。 [numeric:eq:100]
  3. [ACTION|TRANSFORM|Product|Product|NONE] 入力DTOを Product に変換する。
  4. [ACTION|PERSIST|Product|Product|DB] Repository に保存して結果を受け取る。
  5. [ACTION|RETURN|ProductResponse|ProductResponse?|NONE] 保存結果を ProductResponse に変換して返す。
- **Test Cases**:
  - {"id":"tc_product_create_valid","name":"Valid_ReturnsResponse","method":"CreateProduct","arrange":["var repo = new FakeRepo();","var service = new ProductService(repo);","var req = new ProductCreateRequest { Name = \"ItemA\", Price = 10m };"],"act":"var result = service.CreateProduct(req);","assert":["Assert.NotNull(result);","Assert.Equal(\"ItemA\", result!.Name);"]}
  - {"id":"tc_product_create_null","name":"Null_ReturnsNull","method":"CreateProduct","arrange":["var repo = new FakeRepo();","var service = new ProductService(repo);"],"act":"var result = service.CreateProduct(null);","assert":["Assert.Null(result);"]}

### ProductService.UpdateProduct
- **Input**: id:int, ProductCreateRequest
- **Output**: ProductResponse or null
- **Steps**:
  - op:service.update
- **Core Logic**:
  1. [ACTION|VALIDATE|ProductCreateRequest|bool|NONE] 入力が null の場合は null を返す。
  2. [ACTION|VALIDATE|ProductCreateRequest|bool|NONE] Name が空または長さ > 100 の場合は null を返す。 [numeric:eq:100]
  3. [ACTION|FETCH|Product|Product?|NONE] Repository から対象商品を取得する。存在しない場合は null を返す。
  4. [ACTION|TRANSFORM|Product|Product|NONE] 取得した Product に Name/Price を反映する。
  5. [ACTION|PERSIST|Product|ProductResponse?|DB] Repository で更新し、結果を ProductResponse に変換して返す。
- **Test Cases**:
  - {"id":"tc_product_update_valid","name":"Valid_UpdatesFields","method":"UpdateProduct","arrange":["var repo = new FakeRepo();","repo.Items.Add(new Product { Id = 1, Name = \"Old\", Price = 5m, CreatedAt = DateTime.UtcNow });","var service = new ProductService(repo);","var req = new ProductCreateRequest { Name = \"New\", Price = 10m };"],"act":"var result = service.UpdateProduct(1, req);","assert":["Assert.NotNull(result);","Assert.Equal(\"New\", result!.Name);"]}
  - {"id":"tc_product_update_missing","name":"Missing_ReturnsNull","method":"UpdateProduct","arrange":["var repo = new FakeRepo();","var service = new ProductService(repo);","var req = new ProductCreateRequest { Name = \"New\", Price = 10m };"],"act":"var result = service.UpdateProduct(1, req);","assert":["Assert.Null(result);"]}

### ProductService.DeleteProduct
- **Input**: id:int
- **Output**: bool
- **Steps**:
  - op:service.delete
- **Core Logic**:
  1. [ACTION|PERSIST|Product|bool|DB] Repository で削除を実行する。
  2. [ACTION|RETURN|Product|bool|NONE] 成功なら true、失敗なら false を返す。
- **Test Cases**:
  - {"id":"tc_product_delete_true","name":"DeleteTrue_ReturnsTrue","method":"DeleteProduct","arrange":["var repo = new FakeRepo { DeleteResult = true };","var service = new ProductService(repo);"],"act":"var result = service.DeleteProduct(1);","assert":["Assert.True(result);"]}
  - {"id":"tc_product_delete_false","name":"DeleteFalse_ReturnsFalse","method":"DeleteProduct","arrange":["var repo = new FakeRepo { DeleteResult = false };","var service = new ProductService(repo);"],"act":"var result = service.DeleteProduct(1);","assert":["Assert.False(result);"]}

### ProductRepository.FetchAll
- **Input**: none
- **Output**: List<Product> (empty list if none)
- **Steps**:
  - op:repo.fetch_all
- **Core Logic**:
- [data_source|products_db|db] products_db data source
  1. [ACTION|DATABASE_QUERY|Product|List<Product>|DB|products_db|db] [semantic_roles:{"sql":"SELECT Id, Name, Price, CreatedAt FROM Products"}] SELECT Id, Name, Price, CreatedAt FROM Products を実行する。
  2. [ACTION|RETURN|Product|List<Product>|NONE] 結果を Product のリストで返す。
- **Test Cases**:
  - Happy Path: 2件返る場合、2件の Product を返す。
  - Edge Case: 0件の場合は空リストを返す。

### ProductRepository.FetchById
- **Input**: id:int
- **Output**: Product or null
- **Steps**:
  - op:repo.fetch_by_id
- **Core Logic**:
- [data_source|products_db|db] products_db data source
  1. [ACTION|DATABASE_QUERY|Product|Product?|DB|products_db|db] [semantic_roles:{"sql":"SELECT Id, Name, Price, CreatedAt FROM Products WHERE Id = @Id"}] SELECT Id, Name, Price, CreatedAt FROM Products WHERE Id = @Id を実行する。
  2. [ACTION|RETURN|Product|Product?|NONE] 取得できない場合は null。
- **Test Cases**:
  - Happy Path: 存在する場合、Product を返す。
  - Edge Case: 存在しない場合は null を返す。

### ProductRepository.Insert
- **Input**: Product
- **Output**: Product
- **Steps**:
  - op:repo.insert
- **Core Logic**:
- [data_source|products_db|db] products_db data source
  1. [ACTION|PERSIST|Product|Product|DB|products_db|db] [semantic_roles:{"sql":"INSERT INTO Products (Name, Price, CreatedAt) VALUES (@Name, @Price, @CreatedAt)"}] INSERT INTO Products (Name, Price, CreatedAt) VALUES (@Name, @Price, @CreatedAt) を実行する。
  2. [ACTION|RETURN|Product|Product|NONE] 実行結果の Id を反映した Product を返す。
- **Test Cases**:
  - Happy Path: Insert 成功時、Id を含んだ Product を返す。

### ProductRepository.Update
- **Input**: id:int, Product
- **Output**: Product or null
- **Steps**:
  - op:repo.update
- **Core Logic**:
- [data_source|products_db|db] products_db data source
  1. [ACTION|PERSIST|Product|Product?|DB|products_db|db] [semantic_roles:{"sql":"UPDATE Products SET Name=@Name, Price=@Price WHERE Id=@Id"}] UPDATE Products SET Name=@Name, Price=@Price WHERE Id=@Id を実行する。
  2. [ACTION|RETURN|Product|Product?|NONE] 更新件数が0なら null。 [numeric:eq:0]
  3. [ACTION|RETURN|Product|Product?|NONE] 更新成功なら Id を反映した Product を返す。
- **Test Cases**:
  - Happy Path: 更新成功時、更新された Product を返す。
  - Edge Case: 対象が存在しない場合は null を返す。

### ProductRepository.Delete
- **Input**: id:int
- **Output**: bool
- **Steps**:
  - op:repo.delete
- **Core Logic**:
- [data_source|products_db|db] products_db data source
  1. [ACTION|PERSIST|Product|bool|DB|products_db|db] [semantic_roles:{"sql":"DELETE FROM Products WHERE Id=@Id"}] DELETE FROM Products WHERE Id=@Id を実行する。
  2. [ACTION|RETURN|Product|bool|NONE] 影響件数が1以上なら true、0なら false。 [numeric:ge:1] [numeric:eq:0]
- **Test Cases**:
  - Happy Path: 削除成功時 true。
  - Edge Case: 対象が存在しない場合は false。

## Generation Hints (Reusable)

### Entities
- **Primary Entity**: User
- **Primary Key**: Id:int
- **Entity Plural**: Users
- **Create Request DTO**: UserCreateRequest
- **Response DTO**: UserResponse

### DTO Mapping
  - **CreateRequest -> Entity**:
    - Name -> Name
    - Email -> Email
    - UtcNow -> CreatedAt
- **Entity -> Response**:
  - Id -> Id
  - Name -> Name
  - Email -> Email
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
- **SelectAll**: SELECT {columns} FROM {table}
- **SelectById**: SELECT {columns} FROM {table} WHERE {pk} = @Id
- **Insert**: INSERT INTO {table} ({columnsNoPk}) VALUES ({paramsNoPk})
- **Update**: UPDATE {table} SET {assignmentsNoPk} WHERE {pk} = @Id
- **Delete**: DELETE FROM {table} WHERE {pk} = @Id

### Validation Template
- **Required String**: not empty
- **Max Length**: use explicit length per field
- **Format**: allow per-field rules (e.g., email must contain @)

### Entity Specs
- **Entity**: User
  - Plural: Users
  - Create DTO: UserCreateRequest
  - Response DTO: UserResponse
  - Controller: UsersController
  - Service: UserService
  - Repository: UserRepository
  - Routes:
    - GET /users
    - GET /users/{id}
    - POST /users
    - PUT /users/{id}
    - DELETE /users/{id}
  - Create Mapping:
    - Name -> Name
    - Email -> Email
    - UtcNow -> CreatedAt
  - Response Mapping:
    - Id -> Id
    - Name -> Name
    - Email -> Email
    - CreatedAt -> CreatedAt
- **Entity**: Product
  - Plural: Products
  - Create DTO: ProductCreateRequest
  - Response DTO: ProductResponse
  - Controller: ProductsController
  - Service: ProductService
  - Repository: ProductRepository
  - Routes:
    - GET /products
    - GET /products/{id}
    - POST /products
    - PUT /products/{id}
    - DELETE /products/{id}
  - Create Mapping:
    - Name -> Name
    - Price -> Price
    - UtcNow -> CreatedAt
  - Response Mapping:
    - Id -> Id
    - Name -> Name
    - Price -> Price
    - CreatedAt -> CreatedAt
