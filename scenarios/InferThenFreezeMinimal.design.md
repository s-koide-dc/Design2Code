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
1. [ACTION|DATABASE_QUERY|Item|List<Item>|DB|db_main|db] [semantic_roles:{"sql":"SELECT * FROM Users"}] Dapper Query で一覧を取得する (`SELECT * FROM Users`)
2. [ACTION|DISPLAY|Item|void|NONE] [refs:step_1] console_writeline で結果を出力する
### Test Cases
- **Happy Path**:
  - **Scenario**: 一覧取得が成功する。
  - **Input**: なし
  - **Expected Output**: ユーザー一覧が返る。
