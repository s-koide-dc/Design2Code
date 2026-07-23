# NaturalStringEqualPredicate
## 1. Purpose
名前が 'Alice' と等しいユーザーを自然文の条件から抽出する。
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
3. 名前が 'Alice' と等しいユーザーを抽出する
4. 条件に合致したユーザー一覧を表示する
### Test Cases
- **Scenario**: NaturalStringEqualPredicate
- **Expected**: {"runtime_oracle":{"fixtures":[{"path":"users.json","content":"[{\"Name\":\"Alice\"},{\"Name\":\"Bob\"}]"}],"return":true,"stdout":{"contains":["Alice"],"not_contains":["Bob"]}}}
