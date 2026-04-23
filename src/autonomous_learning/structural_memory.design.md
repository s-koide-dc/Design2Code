# Structural Memory Design Document

## 1. Purpose
`StructuralMemory` は、プロジェクトの「構造的理解」をベクトル化して保持します。ファイル名やディレクトリ名だけでなく、コード内のドキュメントコメント、クラス名、メソッド名の意味をベクトル空間に配置することで、AIが「特定の機能を実装するのに最適な場所」や「変更による潜在的な影響範囲」、「重複する機能」を直感的に把握できるようにします。

`SemanticSearchBase` を継承し、ハイブリッド検索（セマンティック検索 + キーワード検索）をサポートします。

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
- **MorphAnalyzer**: キーワード抽出のための形態素解析器

### Output
- **Component Map**: ファイル/クラス/メソッド/関数ごとの意味ベクトルとメタデータ
  - 各コンポーネントの構造:
    - `type`: コンポーネントタイプ（"class", "method", "function"）
    - `name`: コンポーネント名（メソッドの場合は "ClassName.MethodName"）
    - `short_name`: 短縮名（メソッド名のみ、メソッドの場合のみ）
    - `class`: 所属クラス名（メソッドの場合のみ）
    - `file`: ファイルの相対パス
    - `summary`: コンポーネントの要約（ドキュメント文字列を含む）
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
1. **ハイブリッド検索**:
   - ベクトルエンジンによる意味検索と、コンポーネント名へのキーワード一致スコアリングを組み合わせます。
   - 名前一致（+0.5）とサマリー一致（+0.3）をベクトル類似度に加算して最終スコアを算出します。

#### 2.4. 重複検出 (`find_duplicates`)
1. **意味的重複の判定**:
   - 検索結果の類似度が `threshold`（デフォルト: 0.85）を超えるものを重複候補として特定します。
   - 同一機能の再利用を促し、コードの冗長化を防ぎます。

#### 2.5. メソッドコードの取得 (`get_method_code`)
1. インデックスされた情報を元にソースファイルからメソッド本体のコードを抽出します（C#は正規表現、PythonはASTまたは正規表現）。


### Test Cases

#### Happy Path
- **index_project**: 
  - プロジェクト内の全ソースファイルが正しくインデックス化されること
  - クラス、メソッド、関数が個別にインデックス化されること
  - ドキュメント文字列がサマリーに含まれること
- **search_component**: 
  - クエリに関連するコンポーネントが類似度順に返されること
  - ハイブリッド検索が正しく動作すること（セマンティック + キーワード）
- **find_duplicates**: 
  - 類似度がしきい値以上のコンポーネントが重複として検出されること
  - しきい値未満のコンポーネントが除外されること

#### Edge Cases
- **index_project**: 
  - `src/` ディレクトリが存在しない場合、プロジェクト判定に応じて警告または情報ログで終了すること
  - ファイルの読み込みに失敗した場合、エラーなく次のファイルに進むこと
  - AST解析に失敗した場合、そのファイルをスキップすること
  - ベクトル化に失敗した場合、ゼロベクトルを使用すること
- **search_component**: 
  - ベクトルエンジンが利用できない場合、キーワード検索のみで動作すること
  - クエリが空の場合、空のリストを返すこと
- **find_duplicates**: 
  - ベクトルエンジンが準備できていない場合、キーワード検索のみで動作すること
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
  - `os`, `json`, `re`: ファイル操作と正規表現
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

## 7. Future Enhancements
- **増分インデックス**: ファイルの変更を検出して、変更されたファイルのみを再インデックス
- **キャッシュ機構**: 頻繁に検索されるクエリの結果をキャッシュ
- **多言語サポート**: JavaScript, Java等の他の言語のサポート
- **より高度なコード抽出**: ASTAnalyzerを使用した正確なメソッドコード抽出
