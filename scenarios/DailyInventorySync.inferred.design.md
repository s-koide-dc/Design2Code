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
1. [ACTION|HTTP_REQUEST|Inventory|string|NONE|inventory_api] [semantic_roles:{"url":"https://inventory.example.com/api/current"}] https://inventory.example.com/api/current から在庫データを取得する
2. [ACTION|JSON_DESERIALIZE|Inventory|List<Inventory>|NONE] [refs:step_1] 取得したデータを JSON デシリアライズして在庫リストに変換する
3. [ACTION|PERSIST|Inventory|void|DB|inventory_db] [semantic_roles:{"sql":"UPDATE Inventory SET Stock = @Stock WHERE Id = @Id"}] 在庫リストの各項目について、SQL 'UPDATE Inventory SET Stock = @Stock WHERE Id = @Id' を実行して在庫情報を更新する
### Test Cases
- **Scenario**: Default
- **Expected**: 1
### Inference Metadata
- inference_mode: infer_then_freeze
- inference_fingerprint: 03088c275bb69a903c7ea83fc8459ff7ac7740f5879d599854eb36a6a7623fd7
- assets:
  - C:\workspace\NLP\config\config.json
  - C:\workspace\NLP\config\project_rules.json
  - C:\workspace\NLP\config\retry_rules.json
  - C:\workspace\NLP\config\safety_policy.json
  - C:\workspace\NLP\config\scoring_rules.json
  - C:\workspace\NLP\resources\dictionary.db
  - C:\workspace\NLP\resources\method_store.json
  - C:\workspace\NLP\resources\vectors\chive-1.3-mc90.txt
