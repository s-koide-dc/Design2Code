# Inference Structural Fallback Design

## Purpose

構造的フォールバックのうちsource系判定を固定順序で実行する。

## Rules

1. stdin、environment、HTTP、file source、裸のfile readの順に判定する。
2. 判定に必要な意味・安全性規則は `DesignInferenceEngine` 側の既存ヘルパーを利用する。
3. JSON復元以降の型依存フォールバックは扱わない。
