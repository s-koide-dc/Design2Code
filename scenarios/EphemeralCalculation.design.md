# EphemeralCalculation
## 1. Purpose
商品の小計を一時的に計算して表示します。エンティティは更新しません。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
1. [ACTION|FETCH|Product|List<Product>|NONE] 'products.json' から商品一覧を読み込む
2. [LOOP|Product|List<Product>|NONE] 各商品について以下の処理を繰り返す
3. [ACTION|CALC|decimal|decimal|NONE] [semantic_roles:{"price_prop":"Price","quantity_prop":"Quantity"}] Price と Quantity を掛け合わせて小計を算出する
4. [ACTION|DISPLAY|decimal|void|NONE] [refs:step_3] 計算された小計を表示する
5. [ACTION|TRANSFORM|Item|void|NONE] [refs:step_4] [END] [refs:step_2]
### Test Cases
- **Scenario**: Default
- **Expected**: true
