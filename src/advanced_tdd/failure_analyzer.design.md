# TestFailureAnalyzer Design Document

## 1. Purpose (Updated 2026-02-10 10:45)
`TestFailureAnalyzer` は、テスト実行結果やビルドログを詳細に分析し、失敗の根本原因を特定して、適切な修正方針を導き出すモジュールです。
新たに「意図と実装の乖離」を検知する機能が追加され、誤ったメソッド選択に対するフィードバックを提供します。

## 2. Structured Specification

### 2.1. テスト失敗分析 (`analyze_test_failure`)
- **Input**: `TestFailure` オブジェクト、(任意) Roslyn 解析データ、(任意) `expected_intent`。
- **Core Logic**:
    1. **原因の分類**: エラーメッセージを `assertion_failure`, `compile_error`, `runtime_error` に分類します。
    2. **セマンティック・ミスマッチ検知 (`_detect_semantic_mismatch`)**:
       - 意図 (`expected_intent`) と、実際に実行されたメソッドの名前やクラス名を照合。
       - キーワードの不整合（例: Intent="PARSE" なのに Method="Serialize"）がある場合、`semantic_mismatch` として検出。
       - これにより、型は合っていても役割が違うコードの使用を防ぎます。
    3. **Deep Stack Analysis**: `assertion_failure` かつ Roslyn データがある場合、スタックトレースの各フレームを走査し、メソッド内の分岐条件とテスト入力を照合します。
    4. **入力値推論**: テストメソッド名（例: `WhenAgeIs20`）から、実行時の入力値や期待値を正規表現で抽出します。
    5. **修正方針の決定**: 
       - **統計的判断**: `RepairKnowledgeBase` の統計を参照し、過去に成功率が高かった方針を選択。
       - **ルールベース**: 統計がない場合は、事前定義された原因-方針マッピングを使用。

### 2.2. コンパイル失敗分析 (`analyze_compilation_failure`)
- **Input**: MSBuild エラーリスト。
- **Logic**: `CS1503`, `CS0029` 等のエラーコードから型不一致を検出し、`ToString()` 追加などの具体的な推奨案を生成します。

## 3. Dependencies
- `RepairKnowledgeBase`, `models.TestFailure`
- `subprocess`, `re`, `json`, `logging`
