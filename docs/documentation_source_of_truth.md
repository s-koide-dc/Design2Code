# Documentation Source of Truth

この文書は、プロジェクト内のドキュメントが同じ方針を重複して説明して内容がずれることを防ぐため、情報ごとの正本を定義します。

## 正本一覧

| 情報 | 正本 | 参照側の責務 |
|---|---|---|
| 公開入口・基本セットアップ | `README.md` | 実行例と概要を掲載し、詳細仕様を重複記載しない |
| 設定項目・設定ファイル | `config/README.md` と `config/*.json` | 設定値の説明と実ファイルを一致させる |
| 全体アーキテクチャ | `docs/project_overview.md` | モジュール責務の要約に限定する |
| 対話・リライト方針 | `docs/dialogue_integration_plan.md` と `config/response_rewriter_config.json` | READMEや設計書は方針を再定義しない |
| CLIの標準出力・標準エラー契約 | `docs/stdout_output_policy.md` | CLI実装とテストはこの契約を参照する |
| 設計書からの生成フロー | `docs/generate_from_design_dataflow.md` | READMEは入口だけを案内する |
| モジュールの入出力・責務 | 各モジュールの `*.design.md` | 別モジュールの設計書へ同じ契約を複製しない |
| 実モデルと派生キャッシュの運用 | `docs/real_vector_model_validation.md` | GitHub上にモデルを配置する前提を書かない |
| 文書参照の検証対象 | `config/doc_reference_policy.json` | 必須・任意・存在確認のみの分類をここで管理する |

`scripts/validate/validate_documentation_consistency.py` は、上記の正本文書の存在、Markdownのローカルリンク、マシン固有のworkspaceパスを検証します。

## 正本ではない文書

- `AI_CHANGELOG.md`: 過去の変更履歴。現行仕様の根拠にはしない。
- `docs/*plan*.md`: 進捗・作業計画。実装状態の最終判定はテストとCI結果を優先する。
- `research/`: 調査・仮説・観測結果。製品仕様を変更する場合は正本へ反映する。

## 更新ルール

1. 仕様を変更する場合は、まず該当する正本を更新する。
2. README、計画書、履歴文書には同じ仕様を全文複製せず、正本への相対リンクを置く。
3. 実装変更時は、対応するモジュール設計書と必要な正本の両方を確認する。
4. 「完了」「実装済み」などの進捗表現には、対応するテスト・検証コマンドを併記する。
