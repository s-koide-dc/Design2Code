# 生成対応契約

この文書は、設計書からC#を生成する経路について、現時点で継続的に検証する範囲を定義する。
対象は `scripts/design/run_design_generation_regression.py` の既定回帰セットであり、機能一覧や自然言語表現一般の受理を保証するものではない。

## 保証の意味

「保証対象」は、固定した資産・設定・設計書のもとで、以下をCIの `generation-quality` ジョブで確認することを表す。

1. 設計書を構造化してC#を生成できる。
2. CodeBuilder/Roslynによる保守性ゲートを通る。
3. 設計書に明示した `runtime_oracle` がある場合、生成物をコンパイル・実行し、入出力・HTTP・SQLiteなどの期待結果を検証する。

これは任意の自然言語、任意の外部サービス、任意のスキーマに対する成功保証ではない。明示情報が不足する、または契約外の組合せである場合は、推測で生成を継続せず、診断または `unverified` として扱う。

## 保証対象

| ゴールデンパス | 主な処理 | 根拠シナリオ | 実行時確認 |
|---|---|---|---|
| ファイルJSON検索 | ファイル読込、JSON復元、連続LINQフィルタ、表示 | `ComplexLinqSearch` | fixture、戻り値、標準出力 |
| CSV集計・書出し | CSV読込、行処理、商品別集計、CSV化、ファイル保存、戻り値 | `CsvSalesAggregation` | fixture、戻り値、出力ファイル |
| HTTPカタログ検索 | HTTP GET、JSON復元、数値・文字列フィルタ、表示 | `ProductApiFilteredCatalog` | HTTP要求／応答、戻り値、標準出力 |
| 明示Entity付きHTTP検索 | Entity Specs、HTTP GET、JSON復元、連続LINQフィルタ、表示 | `CustomerApiWithEntitySpec` | HTTP要求／応答、戻り値、標準出力 |
| HTTPからSQLite同期 | APIキーheader、HTTP GET、JSON復元、SQLite UPDATE | `DailyInventorySync` | HTTP header、SQLite schema/seed、DB assertion、戻り値 |
| SQLite抽出からHTTP登録 | SQLite SELECT、LINQ、反復、HTTP POST payload | `SecureOrderProcessing` | SQLite schema/seed、HTTP要求body、戻り値 |
| 単件状態更新 | SQLite SELECT、日時代入、SQLite UPDATE | `StateUpdatePersist` | SQLite schema/seed、DB assertion、戻り値 |
| 環境変数の出力 | 環境変数取得、表示 | `AppModeEchoMinimal` | environment fixture、戻り値、標準出力 |

既定回帰セットの正本は [run_design_generation_regression.py](../scripts/design/run_design_generation_regression.py) とする。各シナリオの明示oracleが、この表より詳細な期待結果を定義する。

## 実験対象

以下は実装・個別テスト・サンプルが存在しても、上表と同じ組合せ保証には含めない。

- 設計書からの複数ファイル／Web APIプロジェクト生成
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
