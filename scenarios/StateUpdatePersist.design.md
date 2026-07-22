# StateUpdatePersist
## 1. Purpose
ユーザーの最終ログイン日時を更新し、データベースに保存します。
## 2. Structured Specification
### Input
- **Description**: User Id
- **Type/Format**: int
### Output
- **Description**: status
- **Type/Format**: Task<bool>
### Core Logic
- [data_source|db_1|db] メインデータベース
2. [ACTION|DATABASE_QUERY|User|User|DB|db_1] [semantic_roles:{"sql":"SELECT * FROM Users WHERE Id = @userId","error_policy":"return_default"}] `SELECT * FROM Users WHERE Id = @userId` を実行してIDに一致するユーザーを検索する
3. [ACTION|CALC|DateTime|DateTime|NONE] [semantic_roles:{"assignment_target":"LastLoginAt","datetime":"now"}] LastLoginAt に現在時刻を設定する
4. [ACTION|PERSIST|User|void|DB|db_1] [semantic_roles:{"sql":"UPDATE Users SET LastLoginAt = @LastLoginAt WHERE Id = @Id","error_policy":"return_default"}] [refs:step_2] `UPDATE Users SET LastLoginAt = @LastLoginAt WHERE Id = @Id` を実行してユーザーの変更をデータベースに保存する
### Test Cases
- **Scenario**: Default
- **Expected**: {"runtime_oracle":{"await":true,"method_args":[1],"sqlite":{"schema":["CREATE TABLE Users (Id INTEGER PRIMARY KEY, Name TEXT, Age INTEGER, Email TEXT, Points INTEGER, Price NUMERIC, LastLoginAt TEXT)"],"seed":["INSERT INTO Users (Id, Name, Age, Email, Points, Price, LastLoginAt) VALUES (1, 'Alice', 20, 'alice@example.test', 10, 12.5, '2020-01-01T00:00:00')"]},"return":true,"db_assertions":[{"query":"SELECT LastLoginAt FROM Users WHERE Id = 1","not_null":true,"not_equals":"2020-01-01T00:00:00"}]}}
