# UserNamePrefixSearch
## 1. Purpose
'A'で始まる名前のユーザーを抽出して表示します。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
1. 'users.json' を読み込む
2. データをユーザーリストに変換する
3. 名前が 'A' で始まるユーザーを抽出する
4. 条件に合致したユーザー一覧を表示する
### Test Cases
- **Scenario**: Default
- **Expected**: true
