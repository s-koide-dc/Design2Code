# ProductApiFilteredCatalog
## 1. Purpose
商品APIから商品一覧を取得し、在庫があり名前が 'A' で始まる商品だけを表示します。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: Task<bool>
### Core Logic
- [data_source|product_api|http] Product API Endpoint
1. [ACTION|HTTP_REQUEST|Product|string|NETWORK|product_api] [semantic_roles:{"url":"https://api.example.com/products","http_method":"GET","timeout_ms":30000}] 商品APIからJSON文字列を取得する
2. [ACTION|JSON_DESERIALIZE|Product|List<Product>|NONE] [refs:step_1] JSON文字列を商品リストに変換する
3. [ACTION|LINQ|Product|List<Product>|NONE] [refs:step_2] [semantic_roles:{"property":"Stock"}] 在庫が 0 より大きい商品だけを抽出する
4. [ACTION|LINQ|Product|List<Product>|NONE] [refs:step_3] [semantic_roles:{"property":"Name"}] 名前が 'A' で始まる商品だけを抽出する
5. [ACTION|DISPLAY|Product|void|NONE] [refs:step_4] 条件に合致した商品一覧を表示する
### Test Cases
- **Scenario**: Default
- **Expected**: true
