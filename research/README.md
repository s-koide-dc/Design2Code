# Research Workspace

## Purpose

このディレクトリは、本プロジェクトの基礎研究用成果物を分離して管理するための専用領域である。

実装本体の仕様書や運用文書とは分けて、以下を蓄積する。

- 研究テーマごとの整理メモ
- 仮説
- 評価指標
- 実験計画
- 実験結果
- 失敗パターンの分類

## Directory Policy

- 研究テーマごとにサブディレクトリを作成する
- 1 テーマにつき、少なくとも `README.md` を置く
- 実験途中のメモよりも、評価軸と再現手順を優先して記録する
- 場当たり的なルール追加案は、研究上の示唆として整理できる場合のみ残す

## Current Themes

- `ir_meaning_preservation/`

## Recommended Structure Per Theme

- `README.md`: テーマ概要と目的
- `hypotheses.md`: 仮説一覧
- `evaluation.md`: 評価観点と指標
- `cases/`: ベンチマークケース
- `results/`: 実験結果
- `templates/`: 反復運用で使う共通テンプレート

必要になるまでは、空ファイルや空ディレクトリは増やさない。
