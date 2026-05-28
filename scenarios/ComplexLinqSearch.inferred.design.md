# ComplexLinqSearch
## 1. Purpose
'A'で始まる名前、かつ価格が500より大きいユーザーを抽出します。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
1. [ACTION|FETCH|User|string|NONE] 'users.json' を読み込む
2. [ACTION|JSON_DESERIALIZE|User|List<User>|NONE] データをユーザーリストに変換する
3. [ACTION|LINQ|User|List<User>|NONE] [refs:step_2] [semantic_roles:{"property":"Name"}] 名前が 'A' で始まるユーザーを抽出する
4. [ACTION|LINQ|User|List<User>|NONE] [refs:step_3] [semantic_roles:{"property":"Price"}] 価格が 500 より大きいユーザーを抽出する
5. [ACTION|DISPLAY|User|void|NONE] [refs:step_4] 条件に合致したユーザー一覧を表示する
### Test Cases
- **Scenario**: Default
- **Expected**: true
