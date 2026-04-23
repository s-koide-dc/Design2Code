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
1. [CONDITION|EXISTS|string|bool|NONE] "config.json" が存在するかを確認する
2. [ACTION|FETCH|string|string|NONE] [refs:step_1] 設定ファイルを読み込む
3. [ACTION|DISPLAY|string|void|NONE] [refs:step_2] 読み込んだ設定内容を表示する
4. [ELSE|GENERAL] [refs:step_1] ファイルが存在しない場合
5. [ACTION|DISPLAY|string|void|NONE] 「config.json not found」というメッセージを表示する
6. [END|GENERAL] [refs:step_1]
### Test Cases
- **Scenario**: Default
- **Expected**: true
