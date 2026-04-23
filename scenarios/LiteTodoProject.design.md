# LiteTodoProject

## Project Spec

### Tech
- **Target**: net10.0

### Data Access
- **Provider**: SqlServer

### Modules
- **Controller**: TasksController
- **Service**: TaskService
- **Repository**: TaskRepository

### Entities / DTO
- **Entity**: TaskItem
- Id:int
- Title:string
- IsDone:bool
- CreatedAt:DateTime
- **DTO**: TaskCreateRequest
- Title:string
- IsDone:bool
- **DTO**: TaskResponse
- Id:int
- Title:string
- IsDone:bool
- CreatedAt:DateTime

### Validation
- **TaskCreateRequest.Title**: required

## Method Specs

### TaskService.GetTaskItemById
- **Input**: `id:int`
- **Output**: TaskResponse or `null`
- **Core Logic**:
  - [ACTION|FETCH|TaskItem|TaskItem?|NONE] Repository から id で単一の対象を取得する。
  - [ACTION|TRANSFORM|TaskResponse|TaskResponse?|NONE] 取得結果を TaskResponse に変換する。
  - [ACTION|RETURN|TaskResponse|TaskResponse?|NONE] 取得できない場合は null を返す。
- **Test Cases**:
  - **Happy Path**: 存在するIDでDTOが返る。
  - **Edge Case**: 存在しないIDで null が返る。

### TaskService.CreateTaskItem
- **Input**: `TaskCreateRequest req`
- **Output**: TaskResponse or `null`
- **Core Logic**:
  - [ACTION|VALIDATE|TaskCreateRequest|bool|NONE] 入力の必須項目を検証する。
  - [ACTION|TRANSFORM|TaskItem|TaskItem|NONE] DTO をエンティティに変換する。
  - [ACTION|PERSIST|TaskItem|TaskResponse?|DB] Repository に保存し、結果を TaskResponse に変換して返す。
- **Test Cases**:
  - **Happy Path**: 有効な入力で作成結果が返る。
  - **Edge Case**: 入力が不正なら null を返す。

### TaskService.UpdateTaskItem
- **Input**: `id:int, TaskCreateRequest req`
- **Output**: TaskResponse or `null`
- **Core Logic**:
  - [ACTION|VALIDATE|TaskCreateRequest|bool|NONE] 入力が不正なら null を返す。
  - [ACTION|FETCH|TaskItem|TaskItem?|NONE] Repository から対象を取得し、無ければ null を返す。
  - [ACTION|PERSIST|TaskItem|TaskResponse?|DB] 更新内容を反映して保存し、結果を TaskResponse に変換して返す。
- **Test Cases**:
  - **Happy Path**: 有効な入力で更新結果が返る。
  - **Edge Case**: 対象が存在しない場合は null を返す。
