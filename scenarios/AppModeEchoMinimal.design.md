# AppModeEchoMinimal
## 1. Purpose
環境変数からアプリケーションモードを取得して表示します。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
- [data_source|APP_MODE|env] 環境変数 APP_MODE
1. 環境変数 'APP_MODE' を取得する
2. 取得したモードを表示する
### Test Cases
- **Scenario**: Default
- **Expected**: true
