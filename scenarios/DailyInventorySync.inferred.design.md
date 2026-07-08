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
2. [ACTION|JSON_DESERIALIZE|Inventory|List<Inventory>|NONE] [refs:step_1] [semantic_roles:{"error_policy":"return_default"}] 取得したデータを JSON デシリアライズして在庫リストに変換する
3. [ACTION|PERSIST|Inventory|void|DB|inventory_db] [refs:step_2] [semantic_roles:{"sql":"UPDATE Inventory SET Stock = @Stock WHERE Id = @Id","error_policy":"return_default"}] 在庫リストの各項目について、SQL 'UPDATE Inventory SET Stock = @Stock WHERE Id = @Id' を実行して在庫情報を更新する
### Test Cases
- **Scenario**: Default
- **Expected**: 1
