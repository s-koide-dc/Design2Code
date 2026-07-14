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
- **Expected**: {"runtime_oracle":{"await":true,"http_responses":[{"status_code":200,"body":"[{\"Id\":1,\"Name\":\"Alpha\",\"Price\":100,\"Quantity\":3,\"Stock\":3,\"Category\":\"Hardware\",\"DiscountPrice\":90},{\"Id\":2,\"Name\":\"Beta\",\"Price\":200,\"Quantity\":4,\"Stock\":4,\"Category\":\"Hardware\",\"DiscountPrice\":180},{\"Id\":3,\"Name\":\"Atlas\",\"Price\":150,\"Quantity\":0,\"Stock\":0,\"Category\":\"Hardware\",\"DiscountPrice\":140}]"}],"return":true,"stdout":{"contains":["Alpha"],"not_contains":["Beta","Atlas"]},"http_requests":[{"method":"GET","url":"https://api.example.com/products"}]}}
