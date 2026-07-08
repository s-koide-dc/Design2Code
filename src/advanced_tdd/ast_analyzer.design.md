# ASTAnalyzer Design Document

## 1. Purpose
`ASTAnalyzer` は、Python AST または C# Roslyn 解析結果から、クラス構造、メソッド定義、引数情報、循環複雑度、および識別子メタデータを抽出する責任を負います。C# ソース文字列を正規表現で解析しません。

## 2. Structured Specification

### 2.1. Public Methods & Inputs

- **`analyze_code_structure(code: str, language: str, roslyn_data: dict)`**:
    - **Input**: ソースコード文字列、言語 ('python' | 'csharp')、C#用 Roslyn解析データ。
    - **Purpose**: 単一のコードブロックの構造を解析します。
- **`analyze_file(file_path: str)`**:
    - **Input**: ファイルパス。
    - **Purpose**: ファイルを読み込み、拡張子に基づいて言語を判定して構造を解析します。
- **`analyze_directory(dir_path: str, language: str)`**:
    - **Input**: ディレクトリパス、対象言語。
    - **Purpose**: ディレクトリを再帰的に走査し、全対象ファイルの構造情報を統合します。
- **`analyze_stack_trace(stack_trace: str)`**:
    - **Input**: スタックトレース文字列（PythonまたはC#形式）。
    - **Purpose**: スタックトレースからファイルパス、行番号、メソッド名を抽出します。
- **`find_method_dependencies(code: str, method_name: str, language: str)`**:
    - **Input**: コード、メソッド名、言語。
    - **Purpose**: 指定されたメソッド内で呼び出されている他のメソッドや変数を特定します。

### 2.2. Output Data Structures

- **Code Structure (Python/Generic)**:
    - `classes`: クラス定義リスト（メソッド、Docstring、継承情報含む）。
    - `functions`: 関数定義リスト（引数、戻り値、複雑度含む）。
    - `imports`: インポート情報。
    - `variables`: (Python) トップレベル変数定義。
    - `complexity`: 推定循環複雑度。

- **Code Structure (C#)**:
    - `classes`: クラス定義（プロパティ、メソッド含む）。
    - `methods`: (フラットリスト) メソッド定義（アクセス修飾子、戻り値、パラメータ、Docstring）。
    - `properties`: プロパティ定義。
    - `using_statements`: using文リスト。
    - `namespace`: 定義されている名前空間。

- **Directory Analysis Result**:
    - `classes`, `functions`: 各ファイルの定義を統合したリスト。
    - `methods`: メソッド名のフラットリスト（検索用）。
    - `all_identifiers`: Python AST から抽出した識別子セット。
    - `files_analyzed`: 解析したファイル数。

- **Stack Trace Analysis Result**:
    - `stack_depth`: スタックの深さ。
    - `file_locations`: 抽出された位置情報のリスト `[{'file': ..., 'line': ..., 'method': ...}]`。
    - `primary_location`: エラー発生源と思われる最上位の位置情報。
    - `test_context`: テスト失敗に関連する場合、テストファイルとメソッド名。

### 2.3. Core Logic

1.  **言語判定とディスパッチ**: Python は `ast`、C# は Roslyn 解析データだけを使用します。C# の Roslyn データがない場合は `structural_analysis_required` を返します。
2.  **再帰的ディレクトリ解析**: `analyze_directory` は `os.walk` を使用してファイルを探索し、Python の構造と識別子を単一の結果オブジェクトに集約します。C# は Roslyn データなしではスキップします。
3.  **Python AST解析**:
    - `ast.walk` でノードを巡回し、`ClassDef`, `FunctionDef`, `Assign`, `Import` を抽出。
    - 制御フロー構文（If, For, While等）をカウントして循環複雑度を算出。
4.  **C# 構造解析**:
    - MyRoslynAnalyzer の `manifest` と `details_by_id` だけを入力とする。
    - ソーステキストから `namespace`, `class`, `method`, `property`, `using` を推定しない。
5.  **スタックトレース解析**:
    - Python形式 (`File "...", line ...`) と C#形式 (`at ... in ...:line ...` または `at Namespace.Class.Method`) を、固定区切りの文字列走査で構造化データに変換します。
    - スタックトレース解析に正規表現を使いません。


## 3. Test Cases
- **Happy Path (Python)**: 標準的なクラスと関数を含むコードを正しく解析し、メソッド一覧とDocstringを取得できること。
- **Happy Path (C#)**: Roslyn解析結果から、C#のクラス定義とメソッドシグネチャを抽出できること。
- **Edge Case (C#)**: Roslyn解析結果なしでC#ソース文字列だけが渡された場合、構造解析要求の診断を返すこと。
- **Edge Case**: 構文エラーを含むコードが渡された場合、適切にエラーメッセージを返し、システムをクラッシュさせないこと。
