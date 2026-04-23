# MinimalCrudProject

## Purpose

標準 CRUD を対象とした最小の Human Spec で、内部補完が効くことを検証する。

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
- **Controller**: TaskItemsController
  - routes:
  - GET /tasks
  - GET /tasks/{id}
  - POST /tasks
  - PUT /tasks/{id}
  - DELETE /tasks/{id}
- **Service**: TaskItemService
  - methods:
  - GetTaskItems(): List<TaskItemResponse>
  - GetTaskItemById(id:int): TaskItemResponse?
  - CreateTaskItem(req:TaskItemCreateRequest): TaskItemResponse?
  - UpdateTaskItem(id:int, req:TaskItemCreateRequest): TaskItemResponse?
  - DeleteTaskItem(id:int): bool
- **Repository**: TaskItemRepository
  - methods:
  - FetchAll(): List<TaskItem>
  - FetchById(id:int): TaskItem?
  - Insert(item:TaskItem): TaskItem
  - Update(id:int, item:TaskItem): TaskItem?
  - Delete(id:int): bool

### Entities / DTO
- **Entity**: TaskItem
  - Id:int
  - Title:string
  - IsDone:bool
  - CreatedAt:datetime
- **DTO**: TaskItemCreateRequest
  - Title:string
  - IsDone:bool
- **DTO**: TaskItemResponse
  - Id:int
  - Title:string
  - IsDone:bool
  - CreatedAt:datetime

### Infrastructure
- **Logging**: Console
- **Configuration**: appsettings.json

### Validation
- **TaskItemCreateRequest.Title**: required, max_len=100

## Method Specs

（省略: 標準 CRUD は内部補完対象）
