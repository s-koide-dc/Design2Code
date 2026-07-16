# InferThenFreezeMinimal Design Document

## Purpose
ユーザー一覧を取得して返す最小設計。

### Input
- **Description**: なし
- **Type/Format**: `none`
- **Example**: `none`

### Output
- **Description**: ユーザー一覧
- **Type/Format**: `List<User>`
- **Example**: `[{"Id":1,"Name":"A"}]`

### Core Logic
- [data_source|db_main|db]
1. [ACTION|DATABASE_QUERY|User|List<User>|DB|db_main|db] [semantic_roles:{"sql":"SELECT * FROM Users"}] Dapper Query で一覧を取得する (`SELECT * FROM Users`)
2. [ACTION|DISPLAY|User|void|NONE] [refs:step_1] console_writeline で結果を出力する
### Test Cases
- **Scenario**: 一覧取得が成功する
- **Expected**: {"runtime_oracle":{"await":true,"sqlite":{"schema":["CREATE TABLE Users (Id INTEGER PRIMARY KEY, Name TEXT, Age INTEGER, Email TEXT, Points INTEGER, Price NUMERIC, LastLoginAt TEXT)"],"seed":["INSERT INTO Users (Id, Name, Age, Email, Points, Price, LastLoginAt) VALUES (1, 'Alice', 30, 'alice@example.test', 10, 600, '2026-01-01T00:00:00')"]},"stdout":{"contains":["Alice"]}}}
