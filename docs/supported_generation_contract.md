# 生成対応契約

この文書は、設計書からC#を生成する経路について、現時点で継続的に検証する範囲を定義する。
対象は `scripts/design/run_design_generation_regression.py` の既定回帰セットであり、機能一覧や自然言語表現一般の受理を保証するものではない。

## 保証の意味

「保証対象」は、固定した資産・設定・設計書のもとで、以下をCIの `generation-quality` ジョブで確認することを表す。

1. 設計書を構造化してC#を生成できる。
2. CodeBuilder/Roslynによる保守性ゲートを通る。
3. 設計書に明示した構造化 `logic` がある場合、対応する Blueprint の predicate evidence が同じ条件を保持していることを検証する。
4. 設計書に明示した `runtime_oracle` がある場合、生成物をコンパイル・実行し、入出力・HTTP・SQLiteなどの期待結果を検証する。

`runtime_oracle.exception` では、期待する例外の型名とメッセージを明示できる。例外を期待するケースでもSQLite assertionを併記できるため、例外後にデータが変更されていないことを検証できる。

これは任意の自然言語、任意の外部サービス、任意のスキーマに対する成功保証ではない。明示情報が不足する、または契約外の組合せである場合は、推測で生成を継続せず、診断または `unverified` として扱う。

## 保証対象

| ゴールデンパス | 主な処理 | 根拠シナリオ | 実行時確認 |
|---|---|---|---|
| ファイルJSON検索 | ファイル読込、JSON復元、連続LINQフィルタ、表示 | `ComplexLinqSearch` | fixture、戻り値、標準出力 |
| 複合LINQ検索 | ファイルJSON読込、文字列・数値 predicate、AND 結合、表示 | `ConjunctiveLinqSearch` | fixture、戻り値、標準出力 |
| 選択的LINQ検索 | ファイルJSON読込、文字列・数値 predicate、OR 結合、表示 | `DisjunctiveLinqSearch` | fixture、戻り値、標準出力 |
| 明示条件分岐 | ファイルJSON読込、ループ、数値比較 if/else、表示 | `ExplicitConditionBranch` | true/false 分岐の標準出力 |
| 長い同期・再読込フロー | HTTP GET、JSON復元、連続LINQ、反復SQLite保存、DB再読込、再フィルタ、表示、戻り値 | `LongProductSynchronization` | 採用値・価格境界値・対象外名の3ケースで、HTTP要求、SQLite件数・内容、標準出力、戻り値 |
| CSV集計・書出し | CSV読込、行処理、商品別集計、CSV化、ファイル保存、戻り値 | `CsvSalesAggregation` | fixture、戻り値、出力ファイル |
| HTTPカタログ検索 | HTTP GET、JSON復元、数値・文字列フィルタ、表示 | `ProductApiFilteredCatalog` | HTTP要求／応答、戻り値、標準出力 |
| 明示Entity付きHTTP検索 | Entity Specs、HTTP GET、JSON復元、連続LINQフィルタ、表示 | `CustomerApiWithEntitySpec` | HTTP要求／応答、戻り値、標準出力 |
| HTTPからSQLite同期 | APIキーheader、HTTP GET、JSON復元、SQLite UPDATE | `DailyInventorySync` | HTTP header、SQLite schema/seed、DB assertion、戻り値 |
| SQLite抽出からHTTP登録 | SQLite SELECT、LINQ、反復、HTTP POST payload | `SecureOrderProcessing` | SQLite schema/seed、HTTP要求body、戻り値 |
| 単件状態更新 | SQLite SELECT、日時代入、SQLite UPDATE | `StateUpdatePersist` | SQLite schema/seed、DB assertion、戻り値 |
| 環境変数の出力 | 環境変数取得、表示 | `AppModeEchoMinimal` | environment fixture、戻り値、標準出力 |
| 安全な設定読込 | ファイル存在確認、if/else分岐、ファイル読込、表示 | `RobustConfigLoader` | fixtureあり／なし、戻り値、標準出力 |
| 標準入力の変換 | 標準入力読込、文字列整形、標準出力 | `StdinToStdoutTransform` | stdin fixture、戻り値、標準出力 |
| JSONの数値集計 | JSON読込、反復、decimal集計、表示 | `AggregationSummary` | JSON fixture、戻り値、標準出力 |
| 外部データ同期 | HTTP GET、JSON復元、SQLite INSERT | `SyncExternalData` | HTTP response、SQLite schema、DB assertion、戻り値 |

既定回帰セットの正本は [run_design_generation_regression.py](../scripts/design/run_design_generation_regression.py) とする。各シナリオの明示oracleが、この表より詳細な期待結果を定義する。

## 実験対象

以下は実装・個別テスト・サンプルが存在しても、上表と同じ組合せ保証には含めない。

- 標準入力、任意のファイル形式、追加のDBクエリ形式
- 条件分岐、リトライ、計算、変換、反復の任意組合せ
- 実ベクトルモデル、辞書、生成済みmethod-storeを必要とする対話・意味検索経路
- 任意のNuGet依存、任意の外部HTTPエンドポイント、任意のSQLスキーマ

実験対象を保証対象へ昇格するには、代表設計書、明示 `runtime_oracle`、CIで実行する回帰ケースを追加する。

## 契約外の扱い

次の場合は、機能を類推して成功扱いにしない。

- データソース、型、パス／URL／SQL、入力リンクなどの意味上必要な情報が明示されない。
- 実行時oracleが自然文のみで、判定可能な期待値を持たない。
- 外部サービスやローカル資産がCIの再現可能なfixtureとして用意されない。

この方針により、生成可否と検証済み範囲を区別し、決定論的なローカル生成器としての説明可能性を維持する。

## 検証済みプロジェクト生成

複数ファイルのWeb APIプロジェクト生成は、`resources/verified_project_generation_cases.json` に登録された設計書だけを限定保証する。現在は `OrdersProject`、`SampleProject`、`MinimalCrudProject`、`NotesProject` を対象に、生成プロジェクトのビルドと、生成されたDI配線・HTTP endpoint・SQLite・SQL Server LocalDBの全テストを実行する。これは任意のProject Specや任意スキーマを一般に保証するものではない。

台帳は設計書hash、project generation fingerprint、検証時刻、各テストファミリーの成功証跡を保持する。CIの `sqlserver-generation` ジョブは `scripts/validate/validate_verified_project_generation_cases.py --execute` を実行し、登録済みプロジェクトを再生成して全テストを実行する。

## 検証済み成功例台帳

`resources/verified_generation_cases.json` は、コンパイル・生成品質・runtime oracle をすべて通過した成功例だけを記録する台帳である。各登録には設計書のSHA-256、検証時のgenerator commit、generation fingerprint、compilation fingerprint、generation quality fingerprint、runtime oracle fingerprint、UTC時刻、および検証証跡を残す。指紋は証跡の対象範囲ごとに分離し、無関係な実装変更による再検証を避ける。生成・プロジェクト生成の指紋には、実装に加えて直接読み込む設定、method store、プロジェクトテンプレートも含める。

登録は `scripts/tools/register_verified_generation_case.py --design <path>` で行う。このコマンドは全品質ゲートをその場で実行し、失敗またはoracle未実行のケースを登録しない。CIは台帳のハッシュ整合性を検証し、登録済みケースを再実行する。台帳への登録は成功を再利用・回帰対象化するものであり、新しい生成規則や対応範囲を自動採用するものではない。

## タグ入力を減らす支援の境界

`--assist-literal-tags-http` は、設計文に明示された path / URL / SQL literal だけを `literal_roles_only` として in-memory で補完し、通常の構造化生成と同じ品質・oracle検証に通す。元の設計書は書き換えず、補助結果が検証を通過しても対応範囲や成功例台帳を自動で拡張しない。

step の目的・入出力・参照関係・条件式は、現時点では設計書に構造として必要である。これらをモデルの推測で自動採用して人手ゼロにする経路は設けない。情報欠落時は診断として止め、提案の採否と成功例への昇格は独立した検証操作で扱う。

## 失敗事例台帳

`resources/generation_failure_cases.json` は、完全レビューで再現した失敗を停止段階・明示的な理由コード・修正指針とともに保存する。`scripts/tools/register_generation_failure_case.py --design <path>` は、失敗した設計書だけを登録する。分類はsnapshotの構造化フィールドだけを使用し、ログ文面のキーワード照合や推測では行わない。

失敗例の登録は、新しい生成規則の自動採用や仕様の緩和を意味しない。設計書の不足、生成器の不具合、またはoracleの不備を再現・修正・回帰検証できるようにするための証跡である。

失敗を解消した場合は、`scripts/tools/resolve_generation_failure_case.py --failure-case-id <id> --verified-case-id <id>` を使い、open の失敗ケースを検証済み成功例へリンクする。台帳検証は、resolved ケースが実在する成功ケースとUTC時刻を持つことを必須にする。

生成前の設計書確認には `scripts/validate/review_design_readiness.py --design <path>` を使う。このCLIは明示ステップメタデータとStructuredSpecを検証し、openの失敗台帳に同じ理由コードがある場合だけ、その登録済み修正指針を返す。自由文の類似検索や推測で設計を補完しない。

### コンパクトステップ記法

定型的なACTIONは、完全タグの代わりに `[step|INTENT|TARGET|OUTPUT|...]` と書ける。例えば `[step|FETCH|string|string|source=APP_MODE|source_kind=env]` は、決定的に `[ACTION|FETCH|string|string|IO|APP_MODE|env]` へ展開される。対応intent、副作用、sourceの要否は固定表で定義され、自由文・スコア・キーワードから補完しない。条件分岐、ループ、曖昧な操作は完全タグを使う。

## 正式サポート範囲

正式に設計書から生成を保証する対象は、`resources/supported_generation_designs.json` のみで定義する。各対象は成功事例台帳の `verified_case_id`、または未解決の失敗事例台帳の `failure_case_id` に一対一で結び付く。品質回帰・スモーク回帰・CIのreadiness reviewはこのマニフェストを起点にするため、個別スクリプトに対象設計書を重複記述しない。

失敗事例台帳の `open` ケースは、CIで設計書レビューを再実行し、登録済みの `stage` と `reason` が再現することを確認する。失敗が成功に変わった、または原因が変化した場合はCIを失敗させ、成功台帳への登録または失敗記録の更新を明示的に行う。
