# StdinToStdoutTransform
## 1. Purpose
標準入力の文字列を加工して標準出力に表示します。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
- [data_source|STDIN|stdin] 標準入力
2. [ACTION|FETCH|string|string|IO|STDIN|stdin] 標準入力から1行取得する
3. [ACTION|TRANSFORM|string|string|NONE] [ops:trim_upper] 取得した文字列をトリムし、大文字に変換する
4. [ACTION|DISPLAY|string|void|NONE] 変換結果を表示する
### Test Cases
- **Scenario**: Default
- **Expected**: true
