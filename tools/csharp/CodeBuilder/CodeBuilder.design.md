# CodeBuilder Design Document

## 1. Purpose

`CodeBuilder` は JSON ブループリントから C# コードを生成するツール。  
生成したコードを Roslyn で簡易診断し、結果を JSON で返す。

## 2. Structured Specification

### Input
- **Description**: 標準入力の JSON ブループリント。
- **Type/Format**: `Blueprint` JSON

### Output
- **Description**: 生成コードと診断結果の JSON。
- **Type/Format**: `{"status":"success","code":...,"diagnostics":[...],"has_errors":bool}`

### Core Logic
1. 標準入力から JSON を読み込み `Blueprint` にデシリアライズする。
2. `GenerateCode` でクラス/メソッド/フィールド/追加クラスを生成する。
3. Roslyn でコードをパースし、エラー診断を収集する。
4. `__CODEBUILDER_JSON_START__/END` で結果 JSON を出力する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 最小の Blueprint 入力。
  - **Expected Output**: `status == "success"` かつ `code` を返す。
- **Edge Cases**:
  - **Scenario**: JSON 解析失敗。
  - **Expected Output / Behavior**: `status == "error"`。

## 3. Dependencies
- **External**: `Microsoft.CodeAnalysis`, `System.Text.Json`
