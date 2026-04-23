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
2. [ACTION|DATABASE_QUERY|User|User|DB|db_1] [semantic_roles:{"sql": "SELECT * FROM Users WHERE Id = @userId"}] `SELECT * FROM Users WHERE Id = @userId` を実行してIDに一致するユーザーを検索する
3. [ACTION|CALC|DateTime|DateTime|NONE] [semantic_roles:{"assignment_target":"LastLoginAt","datetime":"now"}] LastLoginAt に現在時刻を設定する
4. [ACTION|PERSIST|User|void|DB|db_1] [semantic_roles:{"sql":"UPDATE Users SET LastLoginAt = @LastLoginAt WHERE Id = @Id"}] [refs:step_2] `UPDATE Users SET LastLoginAt = @LastLoginAt WHERE Id = @Id` を実行してユーザーの変更をデータベースに保存する
### Test Cases
- **Scenario**: Default
- **Expected**: true
