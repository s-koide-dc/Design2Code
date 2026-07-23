# Runtime Oracle Executor Design Document

## 1. Purpose

`runtime_oracle_executor` は生成コードを設計書の明示runtime oracleで実行し、成功・失敗だけでなく監査可能な実行証跡を返す。

## 2. Structured Specification

### Input
- **Description**: 生成C#、モジュール名、oracle契約、実行verifier。
- **Type/Format**: `str`, `Dict[str, Any]`

### Output
- **Description**: ケース別の実行結果、stdout、fixture manifest、oracle契約。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. ready状態のruntime oracleごとにテストコードを構築して実行する。
2. 成功時もstdout、oracle契約、fixture pathと内容SHA-256を結果へ残す。
3. fixture本文は監査出力へ複製しない。

## 3. Dependencies
- **Internal**: `runtime_oracle_test_builder`
- **External**: verifier implementation

## 4. Notes
- fixture manifestは再現性確認用であり、秘密情報を含み得るfixture内容そのものは出力しない。
- snapshot利用者は、この実行証跡とpredicate preservation contractを同じ監査payloadで確認できる。
