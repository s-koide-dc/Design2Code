# CompactAppMode
## 1. Purpose
コンパクトステップ記法で環境変数を表示する。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
- [data_source|APP_MODE|env] 環境変数 APP_MODE
1. [step|FETCH|string|string|source=APP_MODE|source_kind=env] モードを取得する
2. [step|DISPLAY|string|void] モードを表示する
### Test Cases
- **Scenario**: Default
- **Expected**: true
