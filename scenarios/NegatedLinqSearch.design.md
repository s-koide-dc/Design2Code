# NegatedLinqSearch

## 1. Purpose

名前が A で始まらないユーザーを抽出する。

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
3. [ACTION|LINQ|User|List<User>|NONE] [refs:step_2] [logic:[{"type":"string","variable_hint":"Name","operator":"StartsWith","expected_value":"A","negated":true}]] 名前が A で始まらないユーザーを抽出する
4. [ACTION|DISPLAY|User|void|NONE] [refs:step_3] 条件に合致したユーザー一覧を表示する

### Test Cases
- **Scenario**: NegatedPrefix
- **Expected**: {"runtime_oracle":{"fixtures":[{"path":"users.json","content":"[{\"Id\":1,\"Name\":\"Alice\",\"Price\":400},{\"Id\":2,\"Name\":\"Bob\",\"Price\":900}]"}],"return":true,"stdout":{"contains":["Bob"],"not_contains":["Alice"]}}}
