# Inference Metadata Design

## Purpose

設計書推論の書戻し、推論metadataのupsert、固定資産のhashとfingerprintを扱う。推論規則や自然言語の意味判断は扱わない。

## Input / Output

- Input: 設計書本文、更新済みCore Logic、data source、設定由来の資産パス、assist metadata。
- Output: metadata付き設計書本文、またはSHA-256を含む資産・fingerprint情報。

## Rules

1. Core Logic内のdata source宣言を重複なく先頭へ書き戻す。
2. `Inference Metadata` は置換または追加し、同一入力では同一fingerprintを生成する。
3. 欠落資産はサイズ0・空hashとして記録し、推測値を作らない。

## Dependencies

- Standard library: `hashlib`, `json`, `os`.
- Caller: `DesignInferenceEngine`.
