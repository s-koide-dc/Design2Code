# ConjunctiveLinqSearch

## 1. Purpose

名前が A で始まり、かつ価格が 500 より大きいユーザーだけを抽出する。

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
3. [ACTION|LINQ|User|List<User>|NONE] [refs:step_2] [logic:[{"type":"string","variable_hint":"Name","operator":"StartsWith","expected_value":"A"},{"type":"conjunction","value":"AND"},{"type":"numeric","variable_hint":"Price","operator":"Greater","expected_value":500}]] 名前が A で始まり、かつ価格が 500 より大きいユーザーを抽出する
4. [ACTION|DISPLAY|User|void|NONE] [refs:step_3] 条件に合致したユーザー一覧を表示する

### Test Cases

- **Scenario**: Conjunction
- **Expected**: {"runtime_oracle":{"fixtures":[{"path":"users.json","content":"[{\"Id\":1,\"Name\":\"Alice\",\"Price\":600},{\"Id\":2,\"Name\":\"Anne\",\"Price\":400},{\"Id\":3,\"Name\":\"Bob\",\"Price\":900}]"}],"return":true,"stdout":{"contains":["Alice"],"not_contains":["Anne","Bob"]}}}
