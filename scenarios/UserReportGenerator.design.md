# UserReportGenerator
## 1. Purpose
アクティブなユーザーの統計レポートを作成し、ローカルファイルに保存します。
## 2. Structured Specification
### Input
- **Description**: Min Points
- **Type/Format**: int
### Output
- **Description**: file path (失敗時は null)
- **Type/Format**: string?
### Core Logic
- [data_source|user_db|db] User Database
- [data_source|report_path|file] Report Output File
3. [ACTION|DATABASE_QUERY|User|IEnumerable<User>|NONE|user_db] [semantic_roles:{"sql":"SELECT * FROM Users"}] SQL 'SELECT * FROM Users' を実行してユーザー情報を取得する
4. [ACTION|LINQ|User|IEnumerable<User>|NONE] [refs:step_3] [ops:filter_points_gt_input] User の Points が input より大きいユーザーのみを抽出する
5. [ACTION|DISPLAY|User|string|NONE] [refs:step_2] ユーザー情報をレポート用テキストに変換する
6. [ACTION|PERSIST|string|void|NONE|report_path] [semantic_roles:{"path":"report.txt"}] [refs:step_3] レポートを 'report.txt' として保存する
7. [ACTION|RETURN|string|string|NONE] [refs:step_5] 出力ファイルパス 'report.txt' を返す
### Test Cases
- **Scenario**: Default
- **Expected**: {"runtime_oracle":{"await":true,"method_args":[100],"sqlite":{"schema":["CREATE TABLE Users (Id INTEGER PRIMARY KEY, Name TEXT, Age INTEGER, Email TEXT, Points INTEGER, Price NUMERIC, LastLoginAt TEXT)"],"seed":["INSERT INTO Users (Id, Name, Age, Email, Points, Price, LastLoginAt) VALUES (1, 'Alice', 30, 'alice@example.test', 150, 600, '2026-01-01T00:00:00'),(2, 'Bob', 30, 'bob@example.test', 50, 300, '2026-01-02T00:00:00')"]},"return":"report.txt","files":[{"path":"report.txt","contains":["Alice"],"not_contains":["Bob"]}]}}
