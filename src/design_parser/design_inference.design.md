# DesignInferenceEngine Design Document

## 1. Purpose

`DesignInferenceEngine` は明示 metadata が不足する `.design.md` に対して、固定資産と固定ルールに基づく決定的補完を一度だけ行い、その結果を `.inferred.design.md` として固定化する。

## 2. Structured Specification

### Input
- **Description**: 元の `.design.md` パス。必要なら accepted 済みの literal tag suggestion payload も受け取る。
- **Type/Format**: `str`
- **Example**: `"scenarios/sample.design.md"`

### Output
- **Description**: 推論結果ステータス、必要なら出力先 `.inferred.design.md`。
- **Type/Format**: `Dict[str, Any]`
- **Example**: `{"status":"updated","output_path":"...sample.inferred.design.md"}`

### Core Logic
1. 設計書本文を読み込む。必要なら accepted 済みの `semantic_roles.path/url/sql` suggestion を in-memory で差し込む。
2. data source 行を先に収集し、後続ステップの source 解決候補として保持する。
   - 明示 `[data_source|...]` だけでなく、現時点では exact-match の plain source description 語彙も扱う。
   - 既定実装では `標準入力`、`Product API Endpoint`、`Local SQL Database`、裸のファイル名行、および `input_path/output_path` に結び付く `入力CSV` / `出力CSV` を補完対象とする。
3. 各 Core Logic 行について、明示タグがある行はそのまま保持し、無い行のみ補完対象にする。
4. `DesignOpsResolver` と entity 推定を使って、`intent`, `target_entity`, `output_type`, `refs`, `semantic_roles`, `data_source` を決定的に推論する。
   - stripped design のように resolver が `DISPLAY` を返した経路でも、直前 `output_type` が `List<User>` / `IEnumerable<Product>` のような collection なら表示対象 entity は `User` / `Product` に補正する。
   - plain line に URL literal と単一 HTTP data source が残っていれば、resolver が `HTTP_REQUEST` を返した場合も含めて、`API 'https://...' からJSON文字列を取得する` のような行は `HTTP_REQUEST + semantic_roles.url + source_ref=http source` へ補完する。
   - plain line に `環境変数` と `取得/読み` が残り、対応する `env` data source がある場合は `FETCH + source_kind=env + source_ref=that env source` へ補完する。
5. 補完時の内部 semantic intent (`GENERAL`, `FETCH`, `TRANSFORM`, `DISPLAY`, `PERSIST`, `HTTP_REQUEST`, `DATABASE_QUERY`, `JSON_DESERIALIZE`, `LINQ`, `CALC`) と node kind (`ACTION`, `CONDITION`, `LOOP`, `ELSE`, `END`) は `src.utils.semantic_intents` の共通定数を使う。
6. resolver 候補が confidence threshold を下回る場合は、plain source / HTTP / file / JSON deserialize / LINQ / DB persist / ops / display / return などの構造的 fallback を先に試す。
   - fallback が成立する場合は、低信頼な resolver 候補ではなく fallback の metadata を採用する。
   - fallback も成立しない場合は、assist 対象判定と boundary probe の契約に合わせて `NO_CANDIDATE` issue で `blocked` を返す。
7. accepted 済みの literal suggestion は explicit tag を上書きせず、missing な `semantic_roles.path/url/sql` にだけ反映する。
8. 変更があれば元文書は書き換えず、`.inferred.design.md` に書き出す。
9. `### Inference Metadata` ブロックを埋め込み、推論ルール版と asset fingerprint を追跡可能にする。
   - LLM 補助を使った場合は `llm_literal_assist:*` を追記し、provider / model / applied step を残す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 明示 metadata が不足する通常ステップ。
  - **Expected Output**: `.inferred.design.md` が生成され、`status=updated`。
- **Edge Cases**:
  - **Scenario**: confidence が閾値未満。
  - **Expected Output / Behavior**: `status=blocked` と issue 一覧を返す。
  - **Scenario**: 変更不要。
  - **Expected Output / Behavior**: `status=no_change` を返す。

## 3. Dependencies
- **Internal**:
  - `config_manager`
  - `design_doc_parser`
  - `design_ops_resolver`
  - `morph_analyzer`
  - `data_source_utils`
  - `entity_inference`
- **External**: なし

## 4. Notes
- 元の `.design.md` を直接更新しない。規約どおり `.inferred.design.md` を生成する。
- `generate_from_design.py --assist-literal-tags-http` から渡される suggestion payload は、accepted 済みの `literal_roles_only` 結果だけを想定し、`path/url/sql` 以外はここでは反映しない。
- 現在の実装で自動補完している `semantic_roles` は主に `sql`、`path`、`property`、`return_value`、`url`、安全ポリシー上許可された `command`、および明示操作語彙に限定した `ops` である。`env` 補完では literal 役割は増やさず、既存 data source と plain-text fetch 表現だけで復元する。
- stripped design からの復元では、生成コードだけでなく `.inferred.design.md` 自体が回帰対象であり、表示対象 entity・HTTP URL・DB SQL・`return true` などの補完結果も固定契約として扱う。
- 現在の boundary probe では、`ComplexLinqSearch` / `SyncExternalData` ともに `strip_tags` までは clean generation が通る一方、quoted literal を落とすと `NO_CANDIDATE` で blocked になる。つまり URL / SQL / path の literal は現時点の deterministic 補完における必要入力である。
- `ops` は現時点では `trim_upper`、`split_lines`、`csv_serialize`、`aggregate_by_product`、`display_names` のみを明示表現から補完し、必要に応じて `output_type` / `target_entity` も対応する既定値へ補正する。
- resolver が別 intent に寄った後で `TRANSFORM` / `CALC` / `DISPLAY` に補正された場合でも、最終 intent に対して `ops` 推論を再評価する。
- resolver が低信頼候補を返した場合でも、構造的 fallback が成立するなら fallback を優先する。これにより method store の pruning や vector DB 再構築で候補集合が変わっても、明示 literal / data source / refs を保持する authoring reduction variant は決定的に復元される。

## 5. Review Notes
- 2026-06-25: 低信頼 resolver 候補より構造的 fallback を優先し、採用可能な候補がない場合は `LOW_CONFIDENCE` ではなく `NO_CANDIDATE` として boundary/assist 判定へ渡す契約を反映。
