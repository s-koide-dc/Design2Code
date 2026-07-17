# Inference Type Resolution Design

## Purpose

JSON復元、LINQ、表示などで共有するentity決定の優先規則を提供する。

## Input / Output

- Input: 直前出力型、semantic roles、出力型からentityを求める関数。
- Output: entity名、または解決不能を表す`None`。

## Rules

1. 明示された`target_entity`または`entity`を最優先する。
2. 明示roleがない場合だけ、直前出力型からentityを解決する。
3. 解決できない場合は既定entityを発明しない。

## Dependencies

- Standard library only.
- Caller: `DesignInferenceEngine`.
