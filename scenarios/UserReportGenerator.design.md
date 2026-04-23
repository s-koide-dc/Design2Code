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
### Test Cases
- **Scenario**: Default
- **Expected**: 'report.txt'
