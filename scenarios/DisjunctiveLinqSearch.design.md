# DisjunctiveLinqSearch

## 1. Purpose

名前が A で始まる、または価格が 500 より大きいユーザーを抽出する。

## 2. Structured Specification

### Input

- **Description**: None
- **Type/Format**: void

### Output

- **Description**: status
- **Type/Format**: bool

### Core Logic

- [data_source|users_json|file] users.json
1. [step|FETCH|User|string|source=users_json|source_kind=file] [semantic_roles:{"path":"users.json"}] users.json を読み込む
2. [step|JSON_DESERIALIZE|User|List<User>] [refs:step_1] データをユーザーリストに変換する
3. [ACTION|LINQ|User|List<User>|NONE] [refs:step_2] [logic:[{"type":"string","variable_hint":"Name","operator":"StartsWith","expected_value":"A"},{"type":"conjunction","value":"OR"},{"type":"numeric","variable_hint":"Price","operator":"Greater","expected_value":500}]] 名前が A で始まる、または価格が 500 より大きいユーザーを抽出する
4. [step|DISPLAY|User|void] [refs:step_3] 条件に合致したユーザー一覧を表示する

### Test Cases

- **Scenario**: Disjunction
- **Expected**: {"runtime_oracle":{"fixtures":[{"path":"users.json","content":"[{\"Id\":1,\"Name\":\"Alice\",\"Price\":400},{\"Id\":2,\"Name\":\"Bob\",\"Price\":900},{\"Id\":3,\"Name\":\"Carol\",\"Price\":100}]"}],"return":true,"stdout":{"contains":["Alice","Bob"],"not_contains":["Carol"]}}}
