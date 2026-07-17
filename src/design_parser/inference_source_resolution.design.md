# Inference Source Resolution Design

## Purpose

data sourceの種別分類と、environment / stdin / HTTP / file のsource overrideを決定的に選択する。

## Input / Output

- Input: Core Logic行、ステップ番号、宣言済みsource一覧、URL抽出関数。
- Output: 種別ごとのsource一覧、または`source_ref`・`source_kind`・強制intentの組。

## Rules

1. HTTP sourceは単一sourceかつ明示URLがある場合だけ選択する。
2. stdin sourceは先頭ステップかつ単一sourceの場合だけ選択する。
3. file sourceは`input_path` / `output_path`の明示された構造的文脈だけを選択する。

## Dependencies

- Internal: `semantic_intents`.
- Caller: `DesignInferenceEngine`.
