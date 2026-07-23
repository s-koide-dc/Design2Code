# NaturalNumericPredicate

## 1. Purpose

価格が 500 より大きいユーザーを自然文の条件から抽出する。

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
3. [ACTION|LINQ|User|List<User>|NONE] [refs:step_2] [semantic_roles:{"property":"Price"}] [logic:[{"type":"numeric","operator":"Greater","variable_hint":"Price","expected_value":500}]] 価格が 500 より大きいユーザーを抽出する
4. [ACTION|DISPLAY|User|void|NONE] [refs:step_3] 条件に合致したユーザー一覧を表示する
### Test Cases
- **Scenario**: NaturalNumericPredicate
- **Expected**: {"runtime_oracle":{"fixtures":[{"path":"users.json","content":"[{\"Id\":1,\"Name\":\"Alice\",\"Price\":400},{\"Id\":2,\"Name\":\"Bob\",\"Price\":900}]"}],"return":true,"stdout":{"contains":["Bob"],"not_contains":["Alice"]}}}
### Inference Metadata
- inference_mode: infer_then_freeze
- inference_fingerprint: dff9995f27825720e31285c0b6289923df3239af57d73a9928b78c64e20dd756
- assets:
  - C:\workspace\NLP\config\config.json
  - C:\workspace\NLP\config\project_rules.json
  - C:\workspace\NLP\config\retry_rules.json
  - C:\workspace\NLP\config\safety_policy.json
  - C:\workspace\NLP\config\scoring_rules.json
  - C:\workspace\NLP\resources\dictionary.db
  - C:\workspace\NLP\resources\method_store.json
  - C:\workspace\NLP\resources\vectors\chive-1.3-mc90.txt
