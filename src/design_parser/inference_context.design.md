# Inference Context Design

## Purpose

行単位の決定的推論で必要となる状態を不変の入力契約として表現する。

## Fields

- ステップ番号、モジュール名、直前出力型、出力形式、最終ステップ情報
- 直前の永続化先
- 明示semantic roles
- 宣言済みdata source一覧

## Rules

1. context自身は推論・補完を行わない。
2. 呼出し側の可変状態を保持せず、各行の判断に必要なsnapshotだけを持つ。
3. 構造的フォールバックのディスパッチャはこの契約を入力とする。
