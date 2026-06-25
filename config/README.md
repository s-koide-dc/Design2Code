# config/ README

このディレクトリは挙動・ポリシー・運用設定を格納します。  
実行時は `src/config/config_manager.py` がこの配下の JSON を読み込みます。

## 0. 主要入口との対応

主要な入口やスクリプトが、どの設定群を主に前提にするかの目安は次の通りです。

1. `scripts/generate/generate_from_design.py`
   - `config.json`
   - `safety_policy.json`
   - `project_rules.json`
   - `retry_rules.json`
   - `scoring_rules.json`
2. `src/pipeline_core/pipeline_core.py`
   - `config.json`
   - `user_preferences.json`
   - `safety_policy.json`
   - `scoring_rules.json`
3. `scripts/validate/run_tdd.py`
   - `config.json`
   - `retry_rules.json`
4. `scripts/validate_project_consistency.py`
   - `doc_reference_policy.json`
   - `project_rules.json` は直接使わず、実装と docs/設計書の整合のみを見る
5. `scripts/sync/sync_project_dependencies.py`
   - `current_project_context.json` を更新対象として扱う
6. `scripts/tools/manage_vector_db.py`
   - `config.json`
   - `current_project_context.json` は直接使わないが、`resources/` 配下の生成物配置と整合する前提で動く

## 1. 基本設定

- `config.json`  
  中核設定。タスク管理や推論に関する共通セクションを保持。

- `user_preferences.json`  
  ユーザー指向のデフォルト設定（対話・出力の傾向）。

## 2. ポリシー/ルール

- `safety_policy.json`  
  安全性や拒否条件の基準。

- `doc_reference_policy.json`  
  `scripts/validate_project_consistency.py` が監視する恒久 docs の一覧と、一時 docs の区分を保持。
  `required_docs`、`existence_only_docs`、`optional_reference_docs` は文字列配列で保持する。
  README から恒久的に案内する主要 docs は `required_docs` に追加する。
  生成物在庫のように常時存在しないファイル名を列挙する文書は、原則として `required_docs` に入れない。
  その種の文書は `existence_only_docs` に入れて、文書自体の有無だけを監視する。
  作業計画メモのように「存在は任意だが、存在するならリンク整合は守る」文書は `optional_reference_docs` に入れる。
  新規 authoring の実例テンプレートのように、恒久資料ではないが参照される運用ガイドも `optional_reference_docs` に置ける。
  validator の失敗時は、これらが `DOCS (required)`、`DOCS (existence-only)`、`DOCS (optional-reference)` の節名として `stderr` に対応出力される。
  docs mode に属さない問題は `GENERAL` 節に出力される。
  policy を変更したら、まず `python scripts/validate_project_consistency.py` を実行して期待どおりの mode で通るか確認する。
  続けて `python -m unittest tests.integration.test_documented_entrypoints -v` を実行し、docs 監視の回帰が崩れていないことを確認する。
  公開 docs の扱いを変えた場合は、必要に応じて `README.md`、`scripts/README.md`、`resources/README.md` などの mode 注記も同期する。

- `retry_rules.json`  
  再試行条件・回復フローの定義。

- `project_rules.json`  
  プロジェクト生成や構成制約。

- `scoring_rules.json`  
  ルールベースの評価基準（品質判定など）。

## 3. 解析/生成の補助設定

- `error_patterns.json`  
  エラー判定や診断用のパターン。

- `coverage_config.json`  
  カバレッジ解析の設定。

- `refactoring_config.json`  
  リファクタリング分析の設定。

- `cicd_config.json`  
  CI/CD 連携・生成の設定。

- `synthesis_profile.json`  
  生成プロファイル（生成方針や重み付け）。

- `autonomous_learning.json`  
  自律学習の動作設定。

- `response_rewriter_config.json`
  Phase 3 の応答リライト設定。`enabled`、`provider`、`command`、`prompt_contract` などを持つ。
  現在の既定値は `enabled: false` で、決定論的応答を保つ。
  有効化する場合の既定候補は `provider: "openai_compatible_http"` で、LM Studio の OpenAI 互換 server を `http://127.0.0.1:1234/v1/chat/completions`、`model: "qwen2.5-1.5b-instruct"` として使う構成にしている。
  `max_new_tokens: 32` は短文自然化向けの初期値で、まだ遅い場合は 24 などへ下げて再計測する。
  現状の品質確認では、安全性と多ターン継続性は良好だが、通常応答の自然化品質はまだ安定して改善できていないため、既定オンにはしていない。
  安定化のため、既定では `rewrite_allowed_intents` を空配列にし、`rewrite_allowed_action_statuses` は `success` に絞っている。
  この空配列は「まだどの intent も rewrite しない」という明示設定として扱う。そのため `FILE_CREATE` などの作業系完了メッセージに加え、`GENERAL` の標準進捗文や `WEATHER` / `TIME` / `CAPABILITY` の定型応答、意味欠落や含意追加が出やすかった `EMOTIVE` / `FEEDBACK`、改善効果が出なかった `GREETING` / `PERSONAL_Q` / `BYE` / `DEFINITION`、十分自然になった `SMALLTALK` も、明示的に allow-list を広げない限り rewrite しない。
  LM Studio / `llama.cpp server` が起動している環境で試すときだけ `enabled: true` に切り替える。
  `llama.cpp` 系や他のローカル推論サーバーへ切り替える場合は、`endpoint_url` と `model` だけ差し替えれば同じ contract で使える。
  CPU subprocess 経路へ戻したい場合は、`provider: "persistent_subprocess_jsonl"` と `command: ["${PYTHON_EXECUTABLE}", "${WORKSPACE_ROOT}/scripts/response_rewriter_qwen_cpu_server.py"]` を使う。
  one-shot 動作で切り分けたい場合だけ、`provider: "subprocess_stdio"` と `scripts/response_rewriter_qwen_cpu.py` に戻して単発起動で確認する。
  subprocess 経路を使う場合のみ、ローカル Python 環境へ `transformers` と CPU 版 `torch` を入れておく必要がある。
  Windows では、subprocess 経路で Codex/端末が仮想環境外の Python を見ている場合があるため、その場合は `command` の先頭を `C:/workspace/NLP/.venv-rewriter/Scripts/python.exe` のように実 interpreter へ固定する。

## 4. 実行時の一時/可変設定

- `current_project_context.json`  
  実行中のプロジェクト状態を保持する一時ファイル。

## 5. 変更時の注意

- 既存のキーを削除・改名する場合は、`src/config/config_manager.py` と参照箇所を同時に更新してください。
- 生成や解析の分岐に影響する設定は、テストでの再確認が必須です。
