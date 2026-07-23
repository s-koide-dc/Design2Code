# NaturalConjunctivePredicate
## 1. Purpose
名前が 'A' で始まり、かつ価格が 500 より大きいユーザーを抽出する。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
- [data_source|users_json|file] users.json
1. [ACTION|FETCH|User|string|IO|users_json|file] [semantic_roles:{"path":"users.json"}] users.json を読み込む
2. [ACTION|JSON_DESERIALIZE|User|List<User>|NONE] [refs:step_1] データをユーザーリストに変換する
3. 名前が 'A' で始まる、かつ価格が 500 より大きいユーザーを抽出する
4. 条件に合致したユーザー一覧を表示する
### Test Cases
- **Scenario**: NaturalConjunctivePredicate
- **Expected**: {"runtime_oracle":{"fixtures":[{"path":"users.json","content":"[{\"Name\":\"Alice\",\"Price\":600},{\"Name\":\"Anne\",\"Price\":400},{\"Name\":\"Bob\",\"Price\":900}]"}],"return":true,"stdout":{"contains":["Alice"],"not_contains":["Anne","Bob"]}}}
