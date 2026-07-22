# ExplicitConditionBranch

## 1. Purpose

明示された数値条件に応じて、各ユーザーの処理を true / false の分岐へ振り分ける。

## 2. Structured Specification

### Input

- **Description**: None
- **Type/Format**: void

### Output

- **Description**: status
- **Type/Format**: bool

### Core Logic

- [data_source|users_file|file] users.json
1. [ACTION|FETCH|User|List<User>|IO|users_file|file] [semantic_roles:{"path":"users.json"}] ユーザー一覧を JSON ファイルから読み込む
2. [LOOP|GENERAL|User|void|NONE] [refs:step_1] 各ユーザーに対して以下を繰り返す
3. [CONDITION|EXISTS|User|bool|NONE] [refs:step_2] [logic:[{"type":"numeric","variable_hint":"Points","operator":"Greater","expected_value":100}]] Points が 100 より大きい場合
4. [ACTION|DISPLAY|User|void|NONE] [refs:step_3] [semantic_roles:{"property":"Name"}] ユーザー名を表示する
5. [ELSE|GENERAL] [refs:step_3] Points が 100 以下の場合
6. [ACTION|DISPLAY|string|void|NONE] [semantic_roles:{"message":"inactive","output_channel":"stdout"}] inactive を表示する
7. [END|GENERAL] [refs:step_3]
8. [END|GENERAL] [refs:step_2]

### Test Cases

- **Scenario**: TrueAndFalseBranches
- **Expected**: {"runtime_oracle":{"fixtures":[{"path":"users.json","content":"[{\"Id\":1,\"Name\":\"Alice\",\"Points\":150},{\"Id\":2,\"Name\":\"Bob\",\"Points\":50}]"}],"return":true,"stdout":{"contains":["Alice","inactive"],"not_contains":["Bob"]}}}
