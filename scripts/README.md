# scripts/ README

このディレクトリは用途別にサブフォルダ分けしています。`sync_project_map.py` と `validate_project_consistency.py` は運用上の基幹スクリプトとしてトップに残しています。

## 1. Top-level (基幹)

- `scripts/sync_project_map.py`
  - `ai_project_map.json` を同期する。
- `scripts/validate_project_consistency.py`
  - モジュール/設計書/依存関係の整合性を検証する。
  - `resources/` 配下の主要 JSON 資産について、intent / capability / role 語彙が共通定数境界に収まっているかも検証する。
- `scripts/benchmark_response_rewriter.py`
  - 応答リライターの one-shot / persistent 実行時間を測る。
  - 既定では `scripts/response_rewriter_qwen_cpu.py` と `scripts/response_rewriter_qwen_cpu_server.py` を比較する。
  - 実モデルの代わりに `--command` で stub backend を指定して回帰確認もできる。
  - `--model-id` と `--max-new-tokens` で Qwen 系モデル比較にも使える。
  - `--mode http --endpoint-url http://127.0.0.1:8080/v1/chat/completions` で `llama.cpp server` などの OpenAI 互換 endpoint を直接計測できる。
- `scripts/inspect_response_rewriter_quality.py`
  - 固定ケース群に対して、応答リライターがどの程度文面を自然化できているかを確認する。
  - `expected_rewrite`, `eligible_by_gate`, `changed`, `assessment` を JSON で返す。
  - `family_summary` と `case_ids_by_assessment` も返すため、標準の deterministic 進捗文・成功文を preserve できているか、conversational 応答だけが rewrite 対象として残っているかを切り分けやすい。
  - `--family deterministic_progress` や `--family deterministic_success` のように family を絞って再計測できる。
  - `openai_compatible_http` を使えば LM Studio / `llama.cpp server` の整形品質確認にそのまま使える。
- `scripts/run_response_rewriter_conversation_probe.py`
  - 実 backend を使って複数ターン会話を流し、各ターンの intent / clarification 状態 / 応答文を JSON で確認する。
  - `pre_rewrite_text` と `rewrite_applied` も出すため、各ターンで実際に文面自然化が効いたかを確認できる。
  - LM Studio のログと、こちら側の複数ターン応答結果を突き合わせるための手動確認用 CLI。
  - これは `Pipeline` を通すため、`.venv-rewriter` ではなく `requirements.txt` 導入済みの通常環境 Python で実行する。
- `scripts/probe_design_inference_boundary.py`
  - `.design.md` を段階的に劣化させた variant を生成し、`infer_then_freeze` と `generate_from_design` がどこまで耐えられるかを JSON で返す。
  - 現在は `original`, `strip_tags`, `strip_tags_drop_literals`, `strip_tags_drop_plain_sources`, `strip_tags_drop_literals_and_plain_sources` を出力する。
  - `clean_generate` を見ると、return code だけでなく stderr 警告なしで通ったかまで分かる。
- `scripts/probe_design_authoring_reduction.py`
  - 同一 `.design.md` から authoring 削減段階ごとの variant を生成し、どこまで deterministic に保てるか、どこから literal boundary に入るかを JSON で返す。
  - 現在は `original`, `drop_step_meta`, `drop_step_meta_refs`, `drop_step_meta_refs_ops`, `strip_tags_keep_literals`, `strip_tags_drop_literals` を出力する。
  - `--assist-endpoint-url` を付けると、同じ variant 群に対して `literal_roles_only` assist の回復可否も並べて観測できる。
  - `--skip-generate` を使うと inference 比較だけに絞れるため、JSON 契約確認や高速な境界観測に向く。
- `scripts/validate_design_authoring.py`
  - 新規 `.design.md` の初稿が現在の authoring 境界に収まっているかを 1 コマンドで判定する。
  - 既定では `original`, `drop_step_meta`, `drop_step_meta_refs`, `drop_step_meta_refs_ops` が deterministic に通ることと、`strip_tags_drop_literals` が `NO_CANDIDATE` で止まることを検証する。
  - `strip_tags_keep_literals` は情報観測枠で、deterministic に通るか assist 境界に落ちるかを `observations` に記録する。
  - 失敗時は exit code `1`、成功時は exit code `0` で JSON を stdout に返す。
- `scripts/review_design_generation_snapshot.py`
  - 1 本の `.design.md` について、元の設計書、`.inferred.design.md`、最終生成コード、`SpecAuditor` の issue、compile 検証結果を 1 回で JSON とファイル出力へまとめる。
  - 中間表現だけでなく、実際の `.cs` を見て authoring 削減の妥当性を確認したいときのレビュー入口。
  - `--assist-endpoint-url` を付けると `literal_roles_only` assist を含めたレビューもできる。
- `scripts/run_design_generation_regression.py`
  - 複数の `.design.md` をまとめて `review_design_generation_snapshot` と同じ基準で回帰確認する。
  - 既定では `ComplexLinqSearch`, `CsvSalesAggregation`, `DailyInventorySync`, `SecureOrderProcessing`, `AppModeEchoMinimal` を対象にし、`--design` を複数指定すると任意の組み合わせに差し替えられる。
  - 各ケースの `inference_status`, `verification_valid`, `spec_issue_count` と、元の詳細 payload を 1 つの JSON に集約する。
- `scripts/audit_literal_tag_assist_coverage.py`
  - `scenarios/` 配下の `.design.md` を strip して `infer_then_freeze` に流し、`NO_CANDIDATE` で止まるケースと literal assist 推奨ケースを JSON で返す。
  - `assist_recommended` は、blocked 理由が `NO_CANDIDATE` で、かつ explicit literal-bearing candidate が残っているケースだけを示す。
- `scripts/suggest_design_tags.py`
  - `.design.md` を読んで、タグ不足の step 候補を LLM へ送り、提案タグを stdout の JSON として返す。
  - 新しい中間ファイルは作らず、元の `.design.md` も書き換えない。
  - `path` / `url` / `sql` の literal は original line に明示されていない限り reject する。
  - 既定では、quoted path / URL / SQL literal を含む高価値候補に優先的に絞って送る。
  - `--mode literal_roles_only` では `semantic_roles.path/url/sql` だけを提案対象にし、`step_meta` / `refs` の生成を要求しない。
  - `openai_compatible_http` の既定 `model_id` は `qwen2.5-3b-instruct`。
- `scripts/inspect_design_tag_suggestion_quality.py`
  - 固定ケース（現状は `ComplexLinqSearch`, `SyncExternalData`, `DailyInventorySync`, `UserReportGenerator`, `FetchProductInventory` の stripped design）に対して、LLM タグ提案が expected literal suggestion を拾えているかを JSON で返す。
  - `all_expected_found` と `missing_expected` を見ると、安全性だけでなく有効性も測れる。
  - 既定では `literal_roles_only` で計測し、`path/url/sql` 回収だけを分離して評価する。
  - `expected_role_totals` / `matched_role_totals` により、`path` / `url` / `sql` の role 別回収率も確認できる。
  - 現状の既定運用モデルは `qwen2.5-3b-instruct` を想定する。

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
  - `--assist-literal-tags-http` と `--assist-endpoint-url` を付けると、`literal_roles_only` の accepted 提案を in-memory で先に差し込み、その結果を `.inferred.design.md` に記録してから通常の deterministic generation を続ける。
  - 既定の `--assist-policy on_blocked_only` は deterministic 補完が `NO_CANDIDATE` で止まった時だけ backend を呼ぶ。`--assist-policy always` を付けると毎回併用する。
  - accepted されるのは post-validate 済みの `semantic_roles.path/url/sql` だけで、元の `.design.md` は変更しない。
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
