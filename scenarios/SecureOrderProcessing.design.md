# SecureOrderProcessing
## 1. Purpose
未処理の注文をデータベースから取得し、不正な注文を除外した後、配送システムに登録します。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: Task<bool>
### Core Logic
- [data_source|order_db|db] Order Database
- [data_source|shipping_api|http] Shipping API Endpoint
1. [ACTION|DATABASE_QUERY|Order|IEnumerable<Order>|NONE|order_db] [semantic_roles:{"sql":"SELECT * FROM Orders WHERE Status = \"Pending\""}] SQL 'SELECT * FROM Orders WHERE Status = "Pending"' を実行して未処理注文を取得する
2. [ACTION|LINQ|Order|IEnumerable<Order>|NONE] [semantic_roles:{"property":"Total"}] 金額が 0 より大きい注文を抽出する
3. [LOOP|GENERAL|Order|void|NONE] 残った注文それぞれに対して以下を実行する
4. [ACTION|HTTP_REQUEST|Order|string|NETWORK|shipping_api] [semantic_roles:{"url":"https://shipping.example.com/api","payload":"{context}"}] 注文を配送システムに登録する
5. [END|GENERAL]
### Test Cases
- **Scenario**: Default
- **Expected**: {"runtime_oracle":{"await":true,"http_responses":[{"status_code":200,"body":"{}"}],"sqlite":{"schema":["CREATE TABLE Orders (Id INTEGER PRIMARY KEY, Total REAL, CustomerType TEXT, Status TEXT, Discount REAL, Points INTEGER)"],"seed":["INSERT INTO Orders (Id, Total, CustomerType, Status, Discount, Points) VALUES (1, 125.5, 'Standard', 'Pending', 0.0, 10)","INSERT INTO Orders (Id, Total, CustomerType, Status, Discount, Points) VALUES (2, 0.0, 'Standard', 'Pending', 0.0, 20)","INSERT INTO Orders (Id, Total, CustomerType, Status, Discount, Points) VALUES (3, 80.0, 'Standard', 'Shipped', 0.0, 30)"]},"return":true,"http_requests":[{"method":"POST","url":"https://shipping.example.com/api","body":{"contains":["\"Id\":1"],"not_contains":["\"Id\":2","\"Id\":3"]}}]}}
