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
- [data_source|users_json|file] users.json
1. [ACTION|FETCH|User|string|IO|users_json|file] [semantic_roles:{"path":"users.json"}] 'users.json' を読み込む
2. [ACTION|JSON_DESERIALIZE|User|List<User>|NONE] データをユーザーリストに変換する
3. [ACTION|LINQ|User|List<User>|NONE] [refs:step_2] [semantic_roles:{"property":"Name"}] 名前が 'A' で始まるユーザーを抽出する
4. [ACTION|LINQ|User|List<User>|NONE] [refs:step_3] [semantic_roles:{"property":"Price"}] 価格が 500 より大きいユーザーを抽出する
5. [ACTION|DISPLAY|User|void|NONE] [refs:step_4] 条件に合致したユーザー一覧を表示する
### Test Cases
- **Scenario**: Default
- **Expected**: {"runtime_oracle":{"fixtures":[{"path":"users.json","content":"[{\"Id\":1,\"Name\":\"Alice\",\"Age\":30,\"Email\":\"a@example.test\",\"Points\":10,\"Price\":600,\"LastLoginAt\":\"2026-01-01T00:00:00\"},{\"Id\":2,\"Name\":\"Bob\",\"Age\":25,\"Email\":\"b@example.test\",\"Points\":20,\"Price\":900,\"LastLoginAt\":\"2026-01-02T00:00:00\"},{\"Id\":3,\"Name\":\"Anne\",\"Age\":28,\"Email\":\"c@example.test\",\"Points\":30,\"Price\":400,\"LastLoginAt\":\"2026-01-03T00:00:00\"}]"}],"return":true,"stdout":{"contains":["Alice"],"not_contains":["Bob","Anne"]}}}
