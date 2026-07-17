# Inference Line Syntax Design

## Purpose

設計書の番号・箇条書き接頭辞と、JSON文字列を含み得る角括弧metadataの構文境界を解析する。

## Rules

1. 番号付き行と箇条書きの本文を分離する。
2. JSON文字列中の`[` / `]`をmetadata終端として扱わない。
3. 構文不完全時は終端未検出を返し、補完しない。

## Dependencies

- Standard library only.
- Caller: `DesignInferenceEngine`.
