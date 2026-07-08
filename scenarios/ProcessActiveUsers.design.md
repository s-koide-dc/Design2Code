# ProcessActiveUsers
## 1. Purpose
ユーザーを取得し、条件で絞り込んで名前一覧を表示します。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status (読み込み失敗時は false、正常終了時は true)
- **Type/Format**: bool
### Core Logic
- [data_source|users_file|file] users.json
1. [ACTION|FETCH|User|List<User>|IO|users_file|file] [semantic_roles:{"path":"users.json"}] 'users.json' から全てのデータを読み込み、JSON をユーザーリストに変換する
2. [ACTION|LINQ|User|List<User>|NONE] [refs:step_1] [semantic_roles:{"property":"Price"}] 価格が 100 より大きいユーザーのみを抽出する
3. [ACTION|DISPLAY|User|void|NONE] [refs:step_2] [ops:display_names] 抽出されたユーザーの名前一覧を表示する
### Test Cases
- **Scenario**: Default
- **Expected**: true
