# CalculateOrderDiscount
## 1. Purpose
注文を取得し、条件に応じて割引率を計算し保存、ログを出力します。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
- [data_source|orders_file|file] 注文データファイル
1. [ACTION|FETCH|Order|List<Order>|IO|orders_file|file] [semantic_roles:{"path":"orders.json"}] orders.json を読み込み、JSON をデシリアライズして注文リストに変換する
2. [ACTION|CALC|Order|void|NONE] [refs:step_1] [semantic_roles:{"assignment_target":"Discount","value_prop":"Total","rate_rule_1":{"when":{"prop":"Total","op":">","value":5000,"and":{"prop":"CustomerType","op":"==","value":"Premium"}},"rate":0.15},"rate_rule_2":{"rate":0.05}}] 各注文について、合計金額(Total)と顧客タイプ(CustomerType)に基づいて割引率を計算し、Discount に設定する。Total が 5000 より大きく、かつ CustomerType が Premium の場合は Total の 15% を割引額とし、それ以外は Total の 5% を割引額とする
3. [ACTION|DISPLAY|Order|void|NONE] [semantic_roles:{"message":"全ての処理が完了しました。","output_channel":"stdout"}] 全ての処理が完了したことをログに出力する
### Test Cases
- **Scenario**: Default
- **Expected**: {"runtime_oracle":{"fixtures":[{"path":"orders.json","content":"[{\"Id\":1,\"Total\":6000,\"CustomerType\":\"Premium\",\"Discount\":0}]"}],"return":true,"stdout":{"contains":["全ての処理が完了しました。"]}}}
