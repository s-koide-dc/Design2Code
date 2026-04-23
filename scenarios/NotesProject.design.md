# NotesProject

## Purpose

簡略 Human Spec で CRUD 生成が通ることを確認する（Notes）。

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
- **Controller**: NotesController
  - routes:
  - GET /notes
  - GET /notes/{id}
  - POST /notes
  - PUT /notes/{id}
  - DELETE /notes/{id}
- **Service**: NoteService
  - methods:
  - GetNotes(): List<NoteResponse>
  - GetNoteById(id:int): NoteResponse?
  - CreateNote(req:NoteCreateRequest): NoteResponse?
  - UpdateNote(id:int, req:NoteCreateRequest): NoteResponse?
  - DeleteNote(id:int): bool
- **Repository**: NoteRepository
  - methods:
  - FetchAll(): List<Note>
  - FetchById(id:int): Note?
  - Insert(note:Note): Note
  - Update(id:int, note:Note): Note?
  - Delete(id:int): bool

### Entities / DTO
- **Entity**: Note
  - Id:int
  - Title:string
  - Body:string
  - CreatedAt:datetime
- **DTO**: NoteCreateRequest
  - Title:string
  - Body:string
- **DTO**: NoteResponse
  - Id:int
  - Title:string
  - Body:string
  - CreatedAt:datetime

### Validation
- **NoteCreateRequest.Title**: required, max_len=100
- **NoteCreateRequest.Body**: required, max_len=1000

## Method Specs

（省略: 標準 CRUD は内部補完対象）
