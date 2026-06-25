# CsvSalesAggregation
## 1. Purpose
売上CSVを読み込み、商品別の合計金額を集計してCSVに書き出します。
## 2. Structured Specification
### Input
- `input_path`: `string`
- `output_path`: `string`
### Output
- **Description**: output csv path
- **Type/Format**: string?
### Core Logic
- [data_source|input_path|file] 入力CSV
- [data_source|output_path|file] 出力CSV
1. [ACTION|FETCH|string|string|IO|input_path|file] 入力ファイルパスのCSVを読み込む
2. [ACTION|TRANSFORM|string|List<string>|NONE] [ops:split_lines] CSVを行配列に分割する
3. [LOOP|GENERAL|string|void|NONE] CSVの各行を順に処理する
4. [ACTION|CALC|decimal|decimal|NONE] [ops:aggregate_by_product] 各行の1列目を商品名、2列目を金額として商品別に合計金額を集計する
5. [END|GENERAL]
6. [ACTION|TRANSFORM|string|string|NONE] [ops:csv_serialize] 集計結果をCSV形式の文字列に変換する
7. [ACTION|PERSIST|string|void|IO|output_path|file] [semantic_roles:{"path":"output_path"}] 出力ファイルパスにCSVを書き出す
8. [ACTION|TRANSFORM|string|string|NONE] [refs:step_7] [semantic_roles:{"return_value":"output_path"}] 出力ファイルパスを返す
### Test Cases
- **Scenario**: Default
- **Expected**: output file path
### Inference Metadata
- inference_mode: infer_then_freeze
- inference_fingerprint: 7c0aa86487f84a6be86ed2abfaf10105f37ced3cbde53794d884edf83f61c11a
- assets:
  - C:\workspace\NLP\config\config.json
  - C:\workspace\NLP\config\project_rules.json
  - C:\workspace\NLP\config\retry_rules.json
  - C:\workspace\NLP\config\safety_policy.json
  - C:\workspace\NLP\config\scoring_rules.json
  - C:\workspace\NLP\resources\dictionary.db
  - C:\workspace\NLP\resources\method_store.json
  - C:\workspace\NLP\resources\vectors\chive-1.3-mc90.txt
