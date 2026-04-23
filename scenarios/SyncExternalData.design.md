# SyncExternalData
## 1. Purpose
Web APIから商品情報を取得し、ローカルデータベースに同期・保存します。

## 2. Specification

### Input
- **Description**: None
- **Type/Format**: void

### Output
- **Description**: 同期成功フラグ
- **Type/Format**: Task<bool>

### Core Logic
- [data_source|product_api|http] Product API Endpoint
- [data_source|local_db|db] Local SQL Database
3. [ACTION|HTTP_REQUEST|string|string|NETWORK|product_api] [semantic_roles:{"url":"https://api.example.com/products"}] API 'https://api.example.com/products' からJSON文字列を取得する。
4. [ACTION|JSON_DESERIALIZE|Product|IEnumerable<Product>|NONE] 取得したJSONを商品リストに変換する。
5. [ACTION|PERSIST|Product|void|DB|local_db] [semantic_roles:{"sql":"INSERT INTO Products (Name, Price) VALUES (@Name, @Price)"}] [refs:step_2] 商品リストの各項目に対し、SQL 'INSERT INTO Products (Name, Price) VALUES (@Name, @Price)' を実行して保存する。
7. [ACTION|RETURN|bool|bool|NONE] 処理が成功したとして true を返す。
### Test Cases
- **Scenario**: Happy Path
    - **Expected**: true

