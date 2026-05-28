# scripts/ README

このディレクトリは用途別にサブフォルダ分けしています。`sync_project_map.py` と `validate_project_consistency.py` は運用上の基幹スクリプトとしてトップに残しています。

## 1. Top-level (基幹)

- `scripts/sync_project_map.py`
  - `ai_project_map.json` を同期する。
- `scripts/validate_project_consistency.py`
  - モジュール/設計書/依存関係の整合性を検証する。

## 1.1 stdout/stderr 契約

- 正式 CLI は、成功結果と進行表示を `stdout`、異常系と警告を `stderr` に出す。
- この契約は [docs/stdout_output_policy.md](/C:/workspace/NLP/docs/stdout_output_policy.md) で管理する。
- 新しい正式 CLI を追加した場合は:
  - `src/utils/cli_output.py` を使う。
  - `docs/stdout_output_policy.md` を更新する。
  - `tests/integration/test_documented_entrypoints.py` か適切な回帰テストで固定する。
- 例外:
  - `scripts/generate/demo_synthesis.py` のようなデモ・観察用途スクリプトは、正式 CLI 契約の対象外。

## 1.2 docs 監視モード

- `scripts/validate_project_consistency.py` の docs 監視対象は `config/doc_reference_policy.json` で管理する。
- `required_docs`: 恒久公開 docs。存在とローカル参照整合を監視する。
- `existence_only_docs`: 在庫表 docs。文書自体の存在だけを監視する。
- `optional_reference_docs`: 任意 docs。存在は任意だが、存在するならローカル参照整合を監視する。
- validator の失敗出力は `GENERAL`, `DOCS (required)`, `DOCS (existence-only)`, `DOCS (optional-reference)` の節でまとまる。

## 2. data (取得・変換・知識構築)

- `scripts/data/fetch_jmdict.py` : JMdict の取得
- `scripts/data/parse_jmdict.py` : JMdict の変換（dictionary.db 生成）
- `scripts/data/fetch_vectors.py` : chiVe の取得
- `scripts/data/convert_vectors.py` : chiVe のキャッシュ化
- `scripts/data/build_knowledge_base.py` : 知識ベースの構築

## 3. generate (設計書→生成)

- `scripts/generate/generate_from_design.py` : 設計書からコード/プロジェクト生成
- `scripts/generate/demo_synthesis.py` : 合成デモ（必要時のみ）

## 4. validate (検証)

- `scripts/validate/validate_method_store.py` : method_store の検証
- `scripts/validate/validate_ir_meaning_preservation_regression.py` : IR meaning preservation の regression run 記録と関連成果物の整合性検証
- `scripts/validate/run_ir_meaning_preservation_regression.py` : IR meaning preservation の標準 regression 手順（sync / consistency / run-record validation / optional tests）を 1 コマンドで実行し、`Validation Run` 欄用 markdown、該当 `Regression Check`、`Change Summary` / `Affected Claims` / `Benchmark Coverage` / `Downstream Conservatism Check` / `Role Weakening Check` / `Alias Admission Check` / `Output Path Check` / `Deliverables Produced` / `Final Judgment` の下書き block を出力。`--write-draft` で markdown ファイルへ保存可能（既定: `<run_file>.runner_draft.md`、変更時は `--draft-file`）。`--update-run-file` を付けると、生成した draft block を使って target run file を in-place 更新する。
- `scripts/validate/run_unit_smoke.py` : unitテストのスモーク（vector cache を含む）
  - 既定では asset 非依存の `config_manager`, `design_doc_parser`, `dependency_resolver`, `json_deserialize_guard`, `method_store`, `code_synthesizer_integration` を実行
  - `--profile core|parser|synthesis|assets` でカテゴリ単位に絞れる
  - `core`: `test_config_manager`, `test_dependency_resolver`, `test_method_store`
  - `parser`: `test_design_doc_parser`, `test_json_deserialize_guard`
  - `synthesis`: `test_code_synthesizer_integration`
  - `assets`: `test_vector_cache_required`
  - 最短のローカル健全性チェックとしては `python scripts/validate/run_unit_smoke.py --profile core --verbosity 2` が扱いやすい
  - ローカル資産まで含めて確認したい場合は `python scripts/validate/run_unit_smoke.py --profile core --profile parser --profile synthesis --profile assets --verbosity 2`
  - GitHub Actions では `core + parser + synthesis` だけを実行し、chiVe / cache / `dictionary.db` のような未コミット資産には依存しない
  - `--test-target` は profile に追加する形で使える
- `scripts/validate/run_tdd.py` : Advanced TDD の CLI 入口

## 5. sync (同期/更新)

- `scripts/sync/sync_method_store.py` : method_store の同期
- `scripts/sync/sync_project_dependencies.py` : 依存関係の同期

## 6. tools (補助ツール)

- `scripts/tools/manage_vector_db.py` : ベクタDB管理
  - `seed` / `rebuild` / `harvest` / `all` を提供
  - `--root` で対象ワークスペース、`--analysis-path` で harvest 元を上書き可能
- `scripts/tools/prune_backups.py` : backup/ の古いバックアップを整理
- `scripts/tools/suggest_method_capabilities.py` : method capability の提案生成

## 7. scaffold (雛形生成)

- `scripts/scaffold/create_module.sh` / `create_module.ps1` : モジュール作成
- `scripts/scaffold/create_tool.sh` / `create_tool.ps1` : ツール作成

## 8. Safety Confirmation for Generation Scripts

設計書→生成スクリプトは安全性ポリシーのチェックをデフォルトで有効にしています。  
バイパスする場合は **必ず** `--allow-unsafe` と `--confirm` の両方が必要です。

例:
```bash
python scripts/generate/generate_from_design.py --design path/to/module.design.md --allow-unsafe --confirm
```

### 運用ルール（--allow-unsafe 利用時）

許可ケース:
- 安全性監査のため、意図的に危険 intent を含む設計を検証する場合
- 隔離された検証環境（CI/検証用VM）でのみ実行する場合

禁止ケース:
- 本番/実作業環境での生成
- 設計書の出所が不明、または第三者提供の場合
- 自動実行（スケジュール/CI）のデフォルト動作

推奨ルール:
- 通常運用は `--allow-unsafe` を使わない
- 使用時は `--confirm` に加え、理由をログに残す

補足:
 - `python/py` 実行は `scripts/` 配下かつ `python_allowed_scripts` のホワイトリストに限定されます。
 - 新しいスクリプトを追加したら `config/safety_policy.json` の `python_allowed_scripts` に必ず追記すること。
 - 読み取り系コマンド (`cat`, `type`) と一覧コマンド (`ls`, `dir`) は `read_allowed_dirs` に制限されています（現行: `AIFiles`, `config`, `docs`, `scripts`, `src`, `tests`）。
 - さらに `read_blocked_rules` に一致するパスは読み取り/一覧対象として禁止されます（`secret`/`token` はトークン一致のみ）。
 - 新しい機密ファイル名が増えた場合は `config/safety_policy.json` の `read_blocked_rules` に追加すること。

### backup/ の整理
保持ポリシーに沿ってバックアップを整理する場合は以下を実行します。
```bash
python scripts/tools/prune_backups.py --days 30 --max-per-source 50
```
Dry-run で削除対象を確認する場合:
```bash
python scripts/tools/prune_backups.py --days 30 --max-per-source 50 --dry-run
```
CI など定期実行する場合:
```bash
python scripts/tools/prune_backups.py --days 30 --max-per-source 50
```
