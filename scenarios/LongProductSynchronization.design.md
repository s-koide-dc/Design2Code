# LongProductSynchronization

## 1. Purpose

外部商品APIから商品を取得し、名前と価格で絞り込んだ商品だけをローカルDBへ同期し、保存後の一覧を表示する。

## 2. Structured Specification

### Input

- **Description**: None
- **Type/Format**: void

### Output

- **Description**: synchronization status
- **Type/Format**: Task<bool>

### Core Logic

- [data_source|product_api|http] Product API Endpoint
- [data_source|local_db|db] Local SQLite Database
1. [ACTION|HTTP_REQUEST|Product|string|NETWORK|product_api] [semantic_roles:{"url":"https://api.example.com/products","http_method":"GET"}] 商品APIからJSON文字列を取得する
2. [step|JSON_DESERIALIZE|Product|List<Product>] [refs:step_1] 取得したJSONを商品リストに変換する
3. [ACTION|LINQ|Product|List<Product>|NONE] [refs:step_2] [semantic_roles:{"property":"Name"}] [logic:[{"type":"string","variable_hint":"Name","operator":"StartsWith","expected_value":"A"}]] 名前が A で始まる商品だけを抽出する
4. [ACTION|LINQ|Product|List<Product>|NONE] [refs:step_3] [semantic_roles:{"property":"Price"}] [logic:[{"type":"numeric","variable_hint":"Price","operator":"Greater","expected_value":100}]] 価格が 100 より大きい商品だけを抽出する
5. [LOOP|GENERAL|Product|void|NONE] [refs:step_4] 抽出した各商品について以下を繰り返す
6. [ACTION|PERSIST|Product|void|DB|local_db] [refs:step_5] [semantic_roles:{"sql":"INSERT INTO Products (Name, Price) VALUES (@Name, @Price)"}] 商品をローカルDBへ保存する
7. [END|GENERAL] [refs:step_5]
8. [ACTION|DATABASE_QUERY|Product|IEnumerable<Product>|DB|local_db] [semantic_roles:{"sql":"SELECT Id, Name, Price FROM Products"}] 保存済み商品をDBから取得する
9. [ACTION|LINQ|Product|IEnumerable<Product>|NONE] [refs:step_8] [semantic_roles:{"property":"Name"}] [logic:[{"type":"string","variable_hint":"Name","operator":"StartsWith","expected_value":"A"}]] 保存済み商品のうち名前が A で始まる商品を抽出する
10. [LOOP|GENERAL|Product|void|NONE] [refs:step_9] 保存済みの各商品について以下を繰り返す
11. [step|DISPLAY|Product|void] [refs:step_10] [semantic_roles:{"property":"Name"}] 商品名を表示する
12. [END|GENERAL] [refs:step_10]
13. [step|RETURN|bool|bool] [semantic_roles:{"return_value":true}] 同期が成功したとして true を返す

### Test Cases

- **Scenario**: FilterSynchronizeAndDisplay
- **Expected**: {"runtime_oracle":{"await":true,"http_responses":[{"status_code":200,"body":"[{\"Id\":1,\"Name\":\"Alpha\",\"Price\":120},{\"Id\":2,\"Name\":\"Beta\",\"Price\":150},{\"Id\":3,\"Name\":\"Atom\",\"Price\":80}]"}],"sqlite":{"schema":["CREATE TABLE Products (Id INTEGER PRIMARY KEY AUTOINCREMENT, Name TEXT, Price NUMERIC)"],"seed":[]},"return":true,"http_requests":[{"method":"GET","url":"https://api.example.com/products"}],"db_assertions":[{"query":"SELECT COUNT(*) FROM Products","scalar_type":"long","equals":1}],"db_rows":[{"query":"SELECT Name, Price FROM Products ORDER BY Id","columns":[{"name":"Name","scalar_type":"string"},{"name":"Price","scalar_type":"int"}],"rows":[["Alpha",120]]}],"stdout":{"contains":["Alpha"],"not_contains":["Beta","Atom"]}}}

- **Scenario**: PriceBoundaryIsExcluded
- **Expected**: {"runtime_oracle":{"await":true,"http_responses":[{"status_code":200,"body":"[{\"Id\":4,\"Name\":\"AlphaBoundary\",\"Price\":100}]"}],"sqlite":{"schema":["CREATE TABLE Products (Id INTEGER PRIMARY KEY AUTOINCREMENT, Name TEXT, Price NUMERIC)"],"seed":[]},"return":true,"http_requests":[{"method":"GET","url":"https://api.example.com/products"}],"db_assertions":[{"query":"SELECT COUNT(*) FROM Products","scalar_type":"long","equals":0}],"stdout":{"not_contains":["AlphaBoundary"]}}}

- **Scenario**: NonMatchingNameIsExcluded
- **Expected**: {"runtime_oracle":{"await":true,"http_responses":[{"status_code":200,"body":"[{\"Id\":5,\"Name\":\"BetaPremium\",\"Price\":220}]"}],"sqlite":{"schema":["CREATE TABLE Products (Id INTEGER PRIMARY KEY AUTOINCREMENT, Name TEXT, Price NUMERIC)"],"seed":[]},"return":true,"http_requests":[{"method":"GET","url":"https://api.example.com/products"}],"db_assertions":[{"query":"SELECT COUNT(*) FROM Products","scalar_type":"long","equals":0}],"stdout":{"not_contains":["BetaPremium"]}}}

- **Scenario**: UnorderedPersistedRows
- **Expected**: {"runtime_oracle":{"await":true,"http_responses":[{"status_code":200,"body":"[{\"Id\":6,\"Name\":\"AlphaOne\",\"Price\":120},{\"Id\":7,\"Name\":\"AlphaTwo\",\"Price\":130}]"}],"sqlite":{"schema":["CREATE TABLE Products (Id INTEGER PRIMARY KEY AUTOINCREMENT, Name TEXT, Price NUMERIC)"],"seed":[]},"return":true,"http_requests":[{"method":"GET","url":"https://api.example.com/products"}],"db_rows":[{"query":"SELECT Name, Price FROM Products ORDER BY Name DESC","order":"any","columns":[{"name":"Name","scalar_type":"string"},{"name":"Price","scalar_type":"int"}],"rows":[["AlphaOne",120],["AlphaTwo",130]]}]}}

- **Scenario**: HttpFailureReturnsDefaultWithoutPersistence
- **Expected**: {"runtime_oracle":{"await":true,"http_responses":[{"status_code":503,"body":"temporarily unavailable"}],"sqlite":{"schema":["CREATE TABLE Products (Id INTEGER PRIMARY KEY AUTOINCREMENT, Name TEXT, Price NUMERIC)"],"seed":[]},"return":false,"http_requests":[{"method":"GET","url":"https://api.example.com/products"}],"stderr":{"contains":["Error during HTTP_REQUEST"]},"db_assertions":[{"query":"SELECT COUNT(*) FROM Products","scalar_type":"long","equals":0}]}}

- **Scenario**: PersistenceFailureReturnsDefaultWithoutPartialWrite
- **Expected**: {"runtime_oracle":{"await":true,"http_responses":[{"status_code":200,"body":"[{\"Id\":8,\"Name\":\"AlphaPersistFailure\",\"Price\":120}]"}],"sqlite":{"schema":["CREATE TABLE Products (Id INTEGER PRIMARY KEY AUTOINCREMENT, Name TEXT)"],"seed":[]},"return":false,"http_requests":[{"method":"GET","url":"https://api.example.com/products"}],"stderr":{"contains":["Error during PERSIST"]},"db_assertions":[{"query":"SELECT COUNT(*) FROM Products","scalar_type":"long","equals":0}]}}
