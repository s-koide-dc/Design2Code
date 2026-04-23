<!--
NOTE: This document is the Human Spec template.
Machine Spec details (steps/ops/SQL/test JSON) are auto-completed during generation.
For non-standard behavior, explicitly document it here.
Refer to /AIFiles/CONVENTIONS.md for mandatory rules.
-->

# spec_helpers Design Document (Human Spec)

*This document is a template. When creating a new module, replace `spec_helpers` and fill in each section.*

## 1. Purpose

A clear and concise description of the module's responsibility and its role within the project. What problem does it solve?

## 2. Structured Specification

This section is the **single source of truth** for the module's behavior, used to drive implementation and testing.

### Input
- **Description**: What data does this module receive?
- **Type/Format**: e.g., `Array<Object>`, `JSON string`.
- **Example**: (optional)

### Output
- **Description**: What data does this module return?
- **Type/Format**: e.g., `Object`, `boolean`.
- **Example**: (optional)
  - **Nullable**: use `Type?` when the method can return null (e.g., `UserResponse?`).

### Core Logic
A concise, step-by-step description of how inputs are transformed into outputs.
1.  Describe the minimal transformation steps.
2.  Include non-standard rules or branches explicitly.

### Test Cases
- **Happy Path**:
  - **Scenario**: One expected success path.
  - **Expected Output**:
- **Edge Cases**:
  - **Scenario**: One or two failure/boundary cases.
  - **Expected Output / Behavior**:

## 3. Security & Boundary Rules (Optional)
*Define strict security rules, such as path traversal prevention, command whitelisting, or input validation logic, if applicable.*

## 4. Consumers (Optional)
*List other modules that depend on this module. This helps in understanding the impact of changes.*
- **Module A**: Uses this module for X.
- **Module B**: Uses this module for Y.

## 5. Dependencies
- **Internal**: List other modules within this project that this module depends on (e.g., `product_database`).
- **External**: List third-party libraries or packages required (e.g., `axios`).

## 6. Notes (Optional)
Any additional assumptions or clarifications that cannot be captured above.

---

## Appendix: Minimal CRUD Example (Human Spec)

# TaskItems Project (Example)

## Purpose
タスク管理の標準 CRUD を生成する。

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

### Validation
- **TaskItemCreateRequest.Title**: required, max_len=100

## Method Specs
（省略: 標準 CRUD は内部補完対象）

