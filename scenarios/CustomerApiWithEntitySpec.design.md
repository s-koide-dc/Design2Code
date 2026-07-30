# CustomerApiWithEntitySpec
## 1. Purpose
顧客APIから顧客一覧を取得し、ポイントが100より大きく名前が 'A' で始まる顧客だけを表示します。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: Task<bool>
### Entity Specs
- Customer:
  - Id: int
  - Name: string
  - Email: string
  - Points: int
### Core Logic
- [data_source|customer_api|http] Customer API Endpoint
1. [ACTION|HTTP_REQUEST|Customer|string|NETWORK|customer_api] [semantic_roles:{"url":"https://customer.example.com/api/customers","http_method":"GET","timeout_ms":30000}] 顧客APIからJSON文字列を取得する
2. [step|JSON_DESERIALIZE|Customer|List<Customer>] [refs:step_1] JSON文字列を顧客リストに変換する
3. [ACTION|LINQ|Customer|List<Customer>|NONE] [refs:step_2] [semantic_roles:{"property":"Points"}] ポイントが 100 より大きい顧客だけを抽出する
4. [ACTION|LINQ|Customer|List<Customer>|NONE] [refs:step_3] [semantic_roles:{"property":"Name"}] 名前が 'A' で始まる顧客だけを抽出する
5. [step|DISPLAY|Customer|void] [refs:step_4] 条件に合致した顧客一覧を表示する
### Test Cases
- **Scenario**: Default
- **Expected**: {"runtime_oracle":{"await":true,"http_responses":[{"status_code":200,"body":"[{\"Id\":1,\"Name\":\"Alice\",\"Email\":\"alice@example.test\",\"Points\":150},{\"Id\":2,\"Name\":\"Bob\",\"Email\":\"bob@example.test\",\"Points\":300},{\"Id\":3,\"Name\":\"Anne\",\"Email\":\"anne@example.test\",\"Points\":80}]"}],"return":true,"stdout":{"contains":["Alice"],"not_contains":["Bob","Anne"]},"http_requests":[{"method":"GET","url":"https://customer.example.com/api/customers"}]}}
