# semantic_intents Design Document

## 1. Purpose

`semantic_intents` は対話 intent とは別に、IR 生成と code synthesis 内部で使う semantic intent / node kind / runtime role の共通定数を提供し、`GENERAL` / `FETCH` / `TRANSFORM` / `DISPLAY` などの内部語彙を集中管理する。

## 2. Structured Specification

### Input
- **Description**: なし。定数モジュールとして利用される。
- **Type/Format**: N/A

### Output
- **Description**: semantic intent、node kind、runtime role の共通定数。
- **Type/Format**: `str`

### Core Logic
1. `INTENT_GENERAL`、`INTENT_FETCH`、`INTENT_TRANSFORM`、`INTENT_DISPLAY`、`INTENT_DATABASE_QUERY`、`INTENT_JSON_DESERIALIZE`、`INTENT_EXISTS` など、IR/runtime bridge 用の内部 semantic intent を定義する。
2. `NODE_ACTION`、`NODE_CONDITION`、`NODE_LOOP` など、IR ノード種別の共通語彙を定義する。
3. `ROLE_ACTION`、`ROLE_FETCH`、`ROLE_PERSIST`、`ROLE_TRANSFORM`、`ROLE_DISPLAY` など、runtime role の既定値を共通化する。

## 3. Dependencies
- **Internal**: なし
- **External**: なし
