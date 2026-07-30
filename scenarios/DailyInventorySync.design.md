# DailyInventorySync
## 1. Purpose
外部APIから最新の在庫情報を取得し、データベースの情報を更新します。
## 2. Structured Specification
### Input
- **Description**: API Key
- **Type/Format**: string
### Output
- **Description**: updated count
- **Type/Format**: Task<int>
### Core Logic
- [data_source|inventory_db|db] Inventory Database
- [data_source|inventory_api|http] Inventory API Endpoint
1. [ACTION|HTTP_REQUEST|Inventory|string|NONE|inventory_api] [semantic_roles:{"url":"https://inventory.example.com/api/current","http_method":"GET","api_key_header":"X-API-Key","api_key_input":"input_1","timeout_ms":30000,"ops":["use_api_key_header"],"error_policy":"return_default"}] https://inventory.example.com/api/current から在庫データを取得する
2. [step|JSON_DESERIALIZE|Inventory|List<Inventory>] [refs:step_1] [semantic_roles:{"error_policy":"return_default"}] 取得したデータを JSON デシリアライズして在庫リストに変換する
3. [ACTION|PERSIST|Inventory|void|DB|inventory_db] [refs:step_2] [semantic_roles:{"sql":"UPDATE Inventory SET Stock = @Stock WHERE Id = @Id","error_policy":"return_default"}] 在庫リストの各項目について、SQL 'UPDATE Inventory SET Stock = @Stock WHERE Id = @Id' を実行して在庫情報を更新する
### Test Cases
- **Scenario**: Default
- **Expected**: {"runtime_oracle":{"await":true,"method_args":["secret-api-key"],"http_responses":[{"status_code":200,"body":"[{\"Id\":1,\"Stock\":7},{\"Id\":2,\"Stock\":4}]"}],"sqlite":{"schema":["CREATE TABLE Inventory (Id INTEGER PRIMARY KEY, Stock INTEGER)"],"seed":["INSERT INTO Inventory (Id, Stock) VALUES (1, 0)","INSERT INTO Inventory (Id, Stock) VALUES (2, 0)"]},"return":2,"http_requests":[{"method":"GET","url":"https://inventory.example.com/api/current","headers":{"X-API-Key":"secret-api-key"}}],"db_assertions":[{"query":"SELECT Stock FROM Inventory WHERE Id = 1","scalar_type":"int","equals":7},{"query":"SELECT Stock FROM Inventory WHERE Id = 2","scalar_type":"int","equals":4}]}}
