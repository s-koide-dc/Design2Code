# Inference Data Sources Design

## Purpose

Core Logicからdata source宣言を収集し、固定プロファイル、裸のファイル名、入出力aliasから宣言を補完する。

## Input / Output

- Input: Core Logic行、source解決関数、既定sourceプロファイル、入出力仕様。
- Output: `[data_source|<ref>|<kind>]` 宣言の一覧。

## Rules

1. 収集順序を保持する。
2. file source refはファイル名から決定的に生成する。
3. 入出力aliasは対応する仕様名が存在する場合だけ補完する。

## Dependencies

- Standard library only.
- Caller: `DesignInferenceEngine`.
