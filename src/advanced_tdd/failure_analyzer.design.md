# TestFailureAnalyzer Design Document

## 1. Purpose (Updated 2026-02-10 10:45)
`TestFailureAnalyzer` は、テスト実行結果やビルドログを詳細に分析し、失敗の根本原因を特定して、適切な修正方針を導き出すモジュールです。
構造化された実行コンテキストを利用して「意図と実装の乖離」や分岐条件との不一致を検知します。

## 2. Structured Specification

### 2.1. テスト失敗分析 (`analyze_test_failure`)
- **Input**: `TestFailure` オブジェクト、(任意) Roslyn 解析データ、(任意) `expected_intent`、(任意) 構造化された `analysis_context`。
- **Core Logic**:
    1. **原因の分類**: `TestFailure.error_type` に明示された分類を優先します。エラーメッセージの正規表現・キーワード推定では分類しません。
    2. **セマンティック・ミスマッチ検知 (`_detect_semantic_mismatch`)**:
       - `expected_intent` と `analysis_context.executed_role` の明示された役割を完全一致で比較します。
       - メソッド名・クラス名のキーワードから役割を推測しません。
    3. **Deep Stack Analysis**: `assertion_failure` かつ Roslyn データと `analysis_context.input_values` がある場合、スタックフレームのファイル・行番号をメソッドの行範囲と照合し、分岐条件と明示された入力値を評価します。
    4. **入力値の契約**: 入力値は `analysis_context.input_values` の変数名・プロパティ名をキーとする辞書から取得し、テストメソッド名から推論しません。
    5. **修正方針の決定**: 
       - **統計的判断**: `RepairKnowledgeBase` の統計を参照し、過去に成功率が高かった方針を選択。
       - **ルールベース**: 統計がない場合は、事前定義された原因-方針マッピングを使用。
    6. **分析サマリ固定化**: `target_file` / `line_number` / `root_cause` / `fix_direction` / 分岐条件の有無を `analysis_summary` として返し、後段の対話層が再推論せず利用できるようにします。
    7. **構文解析方針**: Roslyn 分岐条件、assertion 出力、スタックトレース、MSBuild エラーは正規表現ではなく専用の決定的パーサで分解します。

### 2.2. コンパイル失敗分析 (`analyze_compilation_failure`)
- **Input**: MSBuild エラーリスト。
- **Logic**: `CS1503`, `CS0029` 等の構造化されたエラーコードを起点に、クォートされた型名または日本語メッセージの固定区切りを決定的に分解して型不一致情報を抽出します。

### 2.3. 実行時失敗分析 (`analyze_runtime_failure`)
- **Input**: 例外情報 (`type`, `message`)。
- **Logic**: 例外型に応じて `AddFileCheck` / `AddJsonValidation` / `AddNetworkRetry` 等の推奨アクションへ写像します。

### 2.4. テストプロセス実行 (`_execute_test`)
- C# / Python / JavaScript ごとに実行ファイルと引数を配列として構築し、`shell=False` で起動する。
- Python は現在のインタープリタから `-m pytest` を実行する。
- JavaScript は `npm test -- --testPathPattern=<path>` として実際の対象ファイルを渡す。
- 対象ファイル名は単一引数として渡し、シェル構文として解釈しない。

## 3. Dependencies
- `RepairKnowledgeBase`, `models.TestFailure`
- `subprocess`, `json`, `logging`

## 4. Review Notes
- 2026-06-29: テスト実行の構造化引数契約とJavaScript対象パスの伝播を反映。
- 2026-06-29: 条件値の数値変換失敗は `TypeError` / `ValueError` に限定して非成立を返し、予期しない例外を握り潰さない。
- 2026-07-07: 正規表現による分類・条件式解析・スタックトレース解析を廃止し、明示された `error_type` と専用パーサに移行。
