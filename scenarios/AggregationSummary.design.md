# AggregationSummary
## 1. Purpose
全注文の合計金額を集計し、総計を出力します。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
1. [ACTION|FETCH|Order|List<Order>|NONE] 'orders.json' から全ての注文を読み込む
2. [ACTION|CALC|decimal|decimal|NONE] [refs:step_1] [semantic_roles:{"aggregation":true,"variable_hint":"total","value_prop":"Total"}] Order の Total を総計に加算する（合計金額を累積する）
3. [ACTION|DISPLAY|decimal|void|NONE] [semantic_roles:{"display_scope":"after_loop","display_var":"total"}] 最終的な総計を最後に1回だけ表示する
### Test Cases
- **Scenario**: Default
- **Expected**: true
