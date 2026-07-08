# RobustConfigLoader
## 1. Purpose
条件分岐とリトライを組み合わせた安全な読み込み。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
- [data_source|config_file|file] config.json
1. [CONDITION|EXISTS|string|bool|NONE] "config.json" が存在するかを確認する
2. [ACTION|FETCH|string|string|IO|config_file|file] [refs:step_1] [semantic_roles:{"path":"config.json"}] 設定ファイルを読み込む
3. [ACTION|DISPLAY|string|void|NONE] [refs:step_2] 読み込んだ設定内容を表示する
4. [ELSE|GENERAL] [refs:step_1] ファイルが存在しない場合
5. [ACTION|DISPLAY|string|void|NONE] [semantic_roles:{"message":"config.json not found","output_channel":"stdout"}] 「config.json not found」というメッセージを表示する
6. [END|GENERAL] [refs:step_1]
### Test Cases
- **Scenario**: Default
- **Expected**: true
