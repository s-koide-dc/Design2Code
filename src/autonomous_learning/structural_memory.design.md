# Structural Memory Design Document

## 1. Purpose
`StructuralMemory` は、プロジェクトのクラス・メソッド・関数を安定した symbol ID と構造メタデータで保持します。明示された型、役割、capability、symbol ID を満たす候補だけを検索対象にします。

`SemanticSearchBase` を継承しますが、キーワード加点や固定重みの合成は行いません。ベクトル距離は構造条件を満たす候補内の順序付けにだけ使用します。

## 2. Structured Specification

### 2.1. 初期化 (`__init__`)
- **Parameters**: 
  - `storage_dir` (str): ストレージディレクトリのパス
  - `config_manager` (ConfigManager): 設定マネージャー（オプション）
  - `vector_engine` (VectorEngine): ベクトルエンジン（オプション）
  - `morph_analyzer` (MorphAnalyzer): 形態素解析器（オプション）
- **Logic**: 
  1. `workspace_root` を `config_manager` から取得（なければカレントディレクトリ）
  2. 親クラス `SemanticSearchBase` を初期化（collection_name="structural_memory"）
  3. `ASTAnalyzer` を初期化
  4. 既存のインデックスを読み込み（`load()`）

### Input
- **Source Code**: プロジェクト内の全ソースファイル（.py, .cs）
- **VectorEngine**: テキストをベクトル変換するエンジン
- **MorphAnalyzer**: ベクトル入力のトークン化に使う解析器

### Output
- **Component Map**: ファイル/クラス/メソッド/関数ごとの意味ベクトルとメタデータ
  - 各コンポーネントの構造:
    - `type`: コンポーネントタイプ（"class", "method", "function"）
    - `name`: コンポーネント名（メソッドの場合は "ClassName.MethodName"）
    - `short_name`: 短縮名（メソッド名のみ、メソッドの場合のみ）
    - `class`: 所属クラス名（メソッドの場合のみ）
    - `file`: ファイルの相対パス
    - `summary`: コンポーネントの要約（ドキュメント文字列を含む）
    - `symbol_id`: 相対ファイルパスと完全名から作る識別子
    - `role`, `capabilities`, `return_type`, `parameters`: 解析器由来の構造情報
    - `start_line`, `end_line`: ソース取得用の行範囲
- **Search Result**: 関連するコンポーネントのリスト（類似度スコア付き）
- **Duplicate Detection**: 重複の可能性があるコンポーネントのリスト

### Core Logic

#### 2.2. プロジェクトのインデックス作成 (`index_project`)
1. **ソースディレクトリの確認**:
   - `workspace_root/src` ディレクトリが存在するか確認し、存在しない場合は終了します。
2. **ファイルの再帰的探索**:
   - `src/` 配下の `.py` と `.cs` ファイルを走査します。
3. **各ファイルの構造解析**:
   - `ASTAnalyzer` によりクラス、メソッド、関数の要約とドキュメント文字列を抽出します。
4. **ベクトル化と一括登録**:
   - 各コンポーネントをベクトル化し、メタデータ（ファイルパス、行番号等）と共に `collection.upsert` で登録・永続化します。
5. **プロパティ名の整形**:
   - プロパティ名が文字列でない場合はインデックス対象から除外します。
6. **名前の正規化**:
   - クラス名/メソッド名/関数名が文字列でない場合は文字列化してインデックスします。
   - 辞書/配列の場合は JSON 文字列化して識別子として使用します。

#### 2.3. コンポーネント検索 (`search_component`)
1. `component_type`, `role`, `capabilities`, `symbol_id`, `return_type` を構造条件として検証します。
   - `role` は完全一致に加え、`FETCH`/`READ` と `PERSIST`/`WRITE` の既定互換関係を許可します。
   - `capabilities` は要求 capability が候補 capability 集合に含まれることを要求します。
   - `symbol_id` と `return_type` は明示値の一致を要求します。
2. ベクトルエンジンがある場合だけ、構造条件を満たした候補を意味距離順に並べます。
3. ベクトルエンジンも構造条件もない場合は、推測順位で全件を返さず空リストを返します。

#### 2.4. 重複検出 (`find_duplicates`)
1. 解析器が明示した `structural_fingerprint` の完全一致だけを重複として返します。
2. fingerprintがない場合は名称や説明から推測せず空リストを返します。

#### 2.5. メソッドコードの取得 (`get_method_code`)
1. インデックスされた `start_line` / `end_line` の範囲からコードを取得します。行範囲がない場合は `None` を返します。


### Test Cases

#### Happy Path
- **index_project**: 
  - プロジェクト内の全ソースファイルが正しくインデックス化されること
  - クラス、メソッド、関数が個別にインデックス化されること
  - ドキュメント文字列がサマリーに含まれること
- **search_component**: 
  - 明示された構造条件を満たすコンポーネントだけが返されること
  - 構造条件を満たす候補内で意味距離順に返されること
- **find_duplicates**: 
  - `structural_fingerprint` が完全一致するコンポーネントが重複として検出されること
  - fingerprint が異なるコンポーネントは、意味的に近くても除外されること

#### Edge Cases
- **index_project**: 
  - `src/` ディレクトリが存在しない場合、プロジェクト判定に応じて警告または情報ログで終了すること
  - ファイルの読み込みに失敗した場合、エラーなく次のファイルに進むこと
  - AST解析に失敗した場合、そのファイルをスキップすること
  - ベクトル化に失敗した場合、ゼロベクトルを使用すること
- **search_component**: 
  - ベクトルエンジンが利用できない場合、明示された構造条件だけで動作すること
  - ベクトルエンジンが利用できず、構造条件もない場合は空のリストを返すこと
- **find_duplicates**: 
  - `structural_fingerprint` がない場合、空リストを返すこと
  - アイテムが存在しない場合、空のリストを返すこと
- **get_method_code**: 
  - ファイルが存在しない場合、`None` を返すこと
  - メソッドが見つからない場合、`None` を返すこと
  - ファイルの読み込みに失敗した場合、エラーログを出力して `None` を返すこと

#### Specific Scenarios
- **Scenario 1: 機能の所在確認**
  - **Input**: "ログを記録する機能はどこ？"
  - **Expected**: `LogManager` やそれに関連するメソッドが上位にランクインすること
  
- **Scenario 2: 重複機能の検出**
  - **Input**: "Calculate average price" の機能を持つメソッドのサマリー
  - **Expected**: 類似した機能を持つ他のメソッドが重複として検出されること
  
- **Scenario 3: メソッドコードの取得**
  - **Input**: メソッドのメタデータ（name, file等）
  - **Expected**: 該当メソッドのソースコードが返されること

## 3. Dependencies
- **Internal**: 
  - `SemanticSearchBase`: 親クラス（ハイブリッド検索機能を提供）
  - `ASTAnalyzer`: コード構造の解析
  - `VectorEngine`: テキストのベクトル化
  - `MorphAnalyzer`: キーワード抽出
  - `ConfigManager`: ワークスペースルートの取得
- **External**: 
  - `os`, `json`: ファイル操作とメタデータ永続化
  - `numpy`: ベクトル操作
  - `logging`: ロギング
  - `pathlib.Path`: パス操作
  - `typing`: 型ヒント

## 4. Integration Points
- **ComplianceAuditor**: 意味的重複の検出に使用
- **AutonomousLearning**: コンポーネント検索と重複検出に使用
- **ActionExecutor**: コード合成時に関連コンポーネントを検索
- **TestGenerator**: テスト生成時に関連メソッドを検索

## 5. Storage Format
- **Collection Name**: "structural_memory"
- **Storage Files**:
  - `{storage_dir}/structural_memory_items.json`: コンポーネントのメタデータ
  - `{storage_dir}/structural_memory_vectors.npy`: ベクトルデータ（numpy配列）

## 6. Performance Considerations
- **インデックス作成**: プロジェクトサイズに応じて数秒〜数分かかる可能性がある
- **バッチ処理**: 全コンポーネントを一括でアップサートすることで効率化
- **ハイブリッド検索**: セマンティック検索とキーワード検索を組み合わせることで精度向上
- **デバッグログ**: 本番環境では無効化することを推奨

## 7. Operational Notes
- `find_duplicates` の候補トレースは `src.utils.stdout_guard.debug_print` を使う opt-in デバッグ出力とする。
- 重複候補の観測は `NLP_DEBUG_STDOUT=1` のときだけ有効化し、通常利用時の stdout は汚さない。
- 2026-07-07: `search_component` の role 制約を UKB と同じ既定互換関係に統一。ベクトル類似度は構造条件を満たす候補内の順序付けに限定する。

## 8. Future Enhancements
- **増分インデックス**: ファイルの変更を検出して、変更されたファイルのみを再インデックス
- **キャッシュ機構**: 頻繁に検索されるクエリの結果をキャッシュ
- **多言語サポート**: JavaScript, Java等の他の言語のサポート
- **より高度なコード抽出**: ASTAnalyzerを使用した正確なメソッドコード抽出
