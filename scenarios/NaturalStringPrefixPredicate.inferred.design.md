# NaturalStringPrefixPredicate

## 1. Purpose

名前が 'A' で始まるユーザーを自然文の条件から抽出する。

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
3. [ACTION|LINQ|User|List<User>|NONE] [refs:step_2] [semantic_roles:{"property":"Name"}] [logic:[{"type":"string","operator":"StartsWith","variable_hint":"Name","expected_value":"A"}]] 名前が 'A' で始まるユーザーを抽出する
4. [ACTION|DISPLAY|User|void|NONE] [refs:step_3] 条件に合致したユーザー一覧を表示する
### Test Cases
- **Scenario**: NaturalStringPrefixPredicate
- **Expected**: {"runtime_oracle":{"fixtures":[{"path":"users.json","content":"[{\"Id\":1,\"Name\":\"Alice\"},{\"Id\":2,\"Name\":\"Bob\"}]"}],"return":true,"stdout":{"contains":["Alice"],"not_contains":["Bob"]}}}
### Inference Metadata
- inference_mode: infer_then_freeze
- inference_fingerprint: 65ad6d7205a02d0bf5de6b53a3da8b155f23de2a350f00f4f39f7981223a0d7f
- assets:
  - C:\workspace\NLP\config\config.json
  - C:\workspace\NLP\config\project_rules.json
  - C:\workspace\NLP\config\retry_rules.json
  - C:\workspace\NLP\config\safety_policy.json
  - C:\workspace\NLP\config\scoring_rules.json
  - C:\workspace\NLP\resources\dictionary.db
  - C:\workspace\NLP\resources\method_store.json
  - C:\workspace\NLP\resources\vectors\chive-1.3-mc90.txt
