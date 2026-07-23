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
3. [ACTION|LINQ|User|List<User>|NONE] [refs:step_2] [semantic_roles:{"property":"Name"}] [logic:[{"type":"string","operator":"Equal","variable_hint":"Name","expected_value":"Alice"}]] 名前が 'Alice' と等しいユーザーを抽出する
4. [ACTION|DISPLAY|User|void|NONE] [refs:step_3] 条件に合致したユーザー一覧を表示する
### Test Cases
- **Scenario**: NaturalStringEqualPredicate
- **Expected**: {"runtime_oracle":{"fixtures":[{"path":"users.json","content":"[{\"Name\":\"Alice\"},{\"Name\":\"Bob\"}]"}],"return":true,"stdout":{"contains":["Alice"],"not_contains":["Bob"]}}}
### Inference Metadata
- inference_mode: infer_then_freeze
- inference_fingerprint: 6fdc397f04f17e95debfefe6d8994bf9d854b281f971ff9115e1b90568215238
- assets:
  - C:\workspace\NLP\config\config.json
  - C:\workspace\NLP\config\project_rules.json
  - C:\workspace\NLP\config\retry_rules.json
  - C:\workspace\NLP\config\safety_policy.json
  - C:\workspace\NLP\config\scoring_rules.json
  - C:\workspace\NLP\resources\dictionary.db
  - C:\workspace\NLP\resources\method_store.json
  - C:\workspace\NLP\resources\vectors\chive-1.3-mc90.txt
