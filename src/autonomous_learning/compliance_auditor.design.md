# Compliance Auditor Design Document

## 1. Purpose
`ComplianceAuditor` は、プロジェクトの規約（`project_rules.json`）および意味的な整合性を自律的に監査します。AIが能動的にコードベースを巡回し、構造的な不備、設計書の品質問題、意味的な重複を発見することで、プロジェクトの「健康状態」を維持し、プロアクティブな改善提案を行います。

## 2. Structured Specification

### 2.1. 初期化 (`__init__`)
- **Parameters**: 
  - `workspace_root` (str): ワークスペースのルートディレクトリ（デフォルト: "."）
  - `structural_memory` (StructuralMemory): コンポーネントの意味ベクトルを保持するメモリ（オプション）
- **Logic**: 
  1. ワークスペースルートを `Path` オブジェクトとして保存
  2. `structural_memory` への参照を保存
  3. ロガーを初期化
  4. `_load_rules()` でプロジェクトルールを読み込み
  5. 監査結果を保存する `findings` リストを初期化

### Input
- **Project Structure**: ファイルシステム上のプロジェクト構造
- **Project Rules**: `resources/project_rules.json` の制約定義
  - `structural_rules`: 構造的な制約のリスト
    - `type`: ルールタイプ（"mandatory_file", "dependency_constraint"）
    - `pattern`: ファイルパターン（例: "src/{module}/{module}.design.md"）
    - `source`: 依存関係チェックの対象ディレクトリ
    - `cannot_depend_on`: 禁止された依存先のリスト
    - `description`: ルールの説明
- **Structural Memory**: コンポーネントの意味ベクトル（`StructuralMemory` インスタンス）
  - `vectors`: numpy配列（N x D）
  - `components`: コンポーネント情報のリスト

### Output
- **Audit Report** (List[Dict[str, Any]]): 発見された違反や改善の提案リスト
  - 各項目の構造:
    - `type`: 違反タイプ（"MANDATORY_FILE_MISSING", "DEPENDENCY_VIOLATION", "DOCUMENT_INCOMPLETE", "SEMANTIC_DUPLICATION"）
    - `severity`: 深刻度（"high", "medium", "low"）
    - `file`: 対象ファイルのパス（相対パス）
    - `message`: 違反の説明
    - `details`: 追加情報（オプション）
- **Proactive Task** (Optional[Dict[str, Any]]): ユーザーに提案する最も重要なタスク
  - `summary`: タスクの要約
  - `message`: ユーザーへのメッセージ
  - `action_type`: アクションタイプ（"REFACTOR", "DOC_GEN", "DOC_REFINE"）
  - `finding`: 関連する監査結果

### Core Logic

#### 2.2. プロジェクトルールの読み込み (`_load_rules`)
1. `resources/project_rules.json` のパスを構築します。
2. ファイルが存在する場合、JSONとして読み込みます。
3. 読み込みに失敗した場合、空の辞書を返します。

#### 2.3. 全項目監査の実行 (`run_full_audit`)
1. `findings` リストをクリアします。
2. 以下の監査を順次実行します：
   - `_audit_mandatory_files()`: 必須ファイルの存在チェック
   - `_audit_document_quality()`: 設計書の品質チェック
   - `_audit_dependencies()`: 依存関係制約のチェック
   - `_audit_semantic_overlaps()`: 意味的な重複のチェック
3. 全ての監査結果を含む `findings` リストを返します。

#### 2.4. 設計書の品質監査 (`_audit_document_quality`)
1. `src/` ディレクトリが存在するか確認します。
2. **プレースホルダーパターンの定義**:
   - "ここにモジュールの目的を記述してください"
   - "ロギングの詳細をここに記述してください"
   - "ロジックの詳細をここに記述してください"
   - "Skeleton only"
   - "TODO:"
3. `src/` ディレクトリを再帰的に走査し、`.design.md` ファイルを検索します。
4. 各設計書ファイルの内容を読み込み、プレースホルダーパターンが含まれているか正規表現で検索します。
5. プレースホルダーが見つかった場合、以下の情報を `findings` に追加します：
   - `type`: "DOCUMENT_INCOMPLETE"
   - `severity`: "low"
   - `file`: 設計書の相対パス
   - `message`: 未記入項目の説明

#### 2.5. 必須ファイルの監査 (`_audit_mandatory_files`)
1. `project_rules.json` から `structural_rules` を取得します。
2. `type` が "mandatory_file" のルールを抽出します。
3. 各ルールに対して `_check_pattern_existence()` を呼び出します。

#### 2.6. パターン存在チェック (`_check_pattern_existence`)
1. `src/` ディレクトリが存在するか確認します。
2. `src/` 直下の各モジュールディレクトリを走査します（`__pycache__` を除外）。
3. パターン内の `{module}` プレースホルダーをモジュール名で置換します。
4. 期待されるファイルパスが存在しない場合、以下の情報を `findings` に追加します：
   - `type`: "MANDATORY_FILE_MISSING"
   - `severity`: "medium"
   - `file`: 期待されるファイルの相対パス
   - `message`: 設計書が見つからない旨の説明

#### 2.7. 依存関係の監査 (`_audit_dependencies`)
1. `project_rules.json` から `structural_rules` を取得します。
2. `type` が "dependency_constraint" のルールを抽出します。
3. 各ルールに対して `_check_imports()` を呼び出します。

#### 2.8. インポートチェック (`_check_imports`)
1. 対象ディレクトリ（`source_prefix`）が存在するか確認します。
2. ディレクトリを再帰的に走査し、`.py` ファイルを検索します。
3. 各Pythonファイルの内容を読み込みます。
4. **禁止された依存先のチェック**:
   - 各禁止対象に対して、正規表現パターンを構築します：
     - `^\s*(import|from)\s+{target.replace("/", ".")}`
   - パターンがファイル内に見つかった場合、以下の情報を `findings` に追加します：
     - `type`: "DEPENDENCY_VIOLATION"
     - `severity`: "high"
     - `file`: 違反ファイルの相対パス
     - `message`: 依存関係違反の説明

#### 2.9. 意味的重複の監査 (`_audit_semantic_overlaps`)
1. `structural_memory` が存在し、`collection.vectors` とコンポーネントが2つ以上あるか確認します。
2. **類似度行列の計算**:
   - `np.dot(vectors, vectors.T)` で全ペアの類似度を計算します。
3. **重複の検出**:
   - 類似度のしきい値を 0.95 に設定します。
   - 上三角行列のみを走査し、類似度がしきい値以上のペアを検出します。
   - 同じファイル内のコンポーネントは除外します。
4. 重複が見つかった場合、以下の情報を `findings` に追加します：
   - `type`: "SEMANTIC_DUPLICATION"
   - `severity`: "low"
   - `message`: 機能の重複が疑われる旨の説明
   - `details`: 両コンポーネントの情報と類似度

#### 2.10. プロアクティブ提案の生成 (`generate_proactive_suggestion`)
1. `findings` が空の場合、`None` を返します。
2. **深刻度によるソート**:
   - 深刻度マップ: {"high": 3, "medium": 2, "low": 1}
   - `findings` を深刻度の降順でソートします。
3. **最も重要な違反の選択**:
   - ソート後の最初の項目を選択します。
4. **違反タイプに応じた提案の生成**:
   - **DEPENDENCY_VIOLATION**: リファクタリングの提案
     - `action_type`: "REFACTOR"
     - `message`: 修正案の作成を提案
   - **MANDATORY_FILE_MISSING**: 設計書の自動生成を提案
     - `action_type`: "DOC_GEN"
     - `message`: 実装から設計書を自動生成することを提案
   - **DOCUMENT_INCOMPLETE**: 設計書の詳細追記を提案
     - `action_type`: "DOC_REFINE"
     - `message`: AIによるロジック分析と補完を提案
5. 提案辞書を返します。

### Test Cases

#### Happy Path
- **run_full_audit**: 
  - プロジェクトルールに基づいて全ての監査が実行され、違反が正しく検出されること
  - 各監査タイプ（必須ファイル、設計書品質、依存関係、意味的重複）が正常に動作すること

#### Edge Cases
- **_audit_mandatory_files**: 
  - `src/` ディレクトリが存在しない場合、エラーなく処理をスキップすること
  - `__pycache__` ディレクトリが正しく除外されること
- **_audit_document_quality**: 
  - 設計書ファイルの読み込みに失敗した場合、エラーなく次のファイルに進むこと
  - 複数のプレースホルダーが含まれる場合、最初の1つのみを報告すること
- **_audit_dependencies**: 
  - 対象ディレクトリが存在しない場合、エラーなく処理をスキップすること
  - ファイルの読み込みに失敗した場合（エンコーディングエラー等）、エラーなく次のファイルに進むこと
- **_audit_semantic_overlaps**: 
  - `structural_memory` が `None` の場合、エラーなく処理をスキップすること
  - コンポーネントが2つ未満の場合、処理をスキップすること
  - 同じファイル内のコンポーネントが重複として報告されないこと
- **generate_proactive_suggestion**: 
  - `findings` が空の場合、`None` を返すこと
  - 未知の違反タイプの場合、`None` を返すこと

#### Specific Scenarios
- **Scenario 1: 依存関係違反の検知**
  - **Context**: `src/utils` のファイルが `src/pipeline_core` をインポートしている
  - **Expected**: 監査レポートに "DEPENDENCY_VIOLATION" が含まれ、severity が "high" であること
  
- **Scenario 2: 機能重複の検知**
  - **Context**: 酷似した役割を持つ2つのクラスが異なるファイルに存在する
  - **Expected**: 監査レポートに "SEMANTIC_DUPLICATION" が含まれ、類似度が 0.95 以上であること
  
- **Scenario 3: 設計書の品質問題**
  - **Context**: 設計書に "TODO:" が含まれている
  - **Expected**: 監査レポートに "DOCUMENT_INCOMPLETE" が含まれること
  
- **Scenario 4: プロアクティブ提案**
  - **Context**: 複数の違反が存在し、最も深刻なものが依存関係違反である
  - **Expected**: `generate_proactive_suggestion()` が "REFACTOR" アクションを提案すること

## 3. Dependencies
- **Internal**: 
  - `StructuralMemory`: コンポーネントの意味ベクトルを提供
- **External**: 
  - `os`, `json`, `re`: ファイル操作と正規表現
  - `numpy`: 類似度行列の計算
  - `logging`: ロギング
  - `pathlib.Path`: パス操作
  - `typing`: 型ヒント

## 4. Integration Points
- **AutonomousLearning**: 監査結果を学習サイクルに統合し、プロアクティブな提案を生成
- **StructuralMemory**: コンポーネントの意味ベクトルを使用して意味的重複を検出
- **ActionExecutor**: プロアクティブ提案に基づいて、設計書生成やリファクタリングを実行

## 5. Configuration
`resources/project_rules.json` の構造例:
```json
{
  "structural_rules": [
    {
      "type": "mandatory_file",
      "pattern": "src/{module}/{module}.design.md",
      "description": "各モジュールには設計書が必要です"
    },
    {
      "type": "dependency_constraint",
      "source": "src/utils",
      "cannot_depend_on": ["src/pipeline_core", "src/planner"],
      "description": "ユーティリティモジュールは上位レイヤーに依存してはいけません"
    }
  ]
}
```

## 6. Output Examples

### 監査レポート例
```python
[
  {
    "type": "MANDATORY_FILE_MISSING",
    "severity": "medium",
    "file": "src/new_module/new_module.design.md",
    "message": "設計書が見つかりません: 各モジュールには設計書が必要です"
  },
  {
    "type": "DOCUMENT_INCOMPLETE",
    "severity": "low",
    "file": "src/old_module/old_module.design.md",
    "message": "設計書に未記入の項目（プレースホルダー）が残っています: 'TODO:'"
  },
  {
    "type": "DEPENDENCY_VIOLATION",
    "severity": "high",
    "file": "src/utils/helper.py",
    "message": "依存関係違反: ユーティリティモジュールは上位レイヤーに依存してはいけません (禁止対象: src/pipeline_core)"
  },
  {
    "type": "SEMANTIC_DUPLICATION",
    "severity": "low",
    "message": "機能の重複が疑われます: 'ComponentA' と 'ComponentB' は極めて類似した役割を持っています。",
    "details": {
      "component1": {"name": "ComponentA", "file": "src/module_a/component.py"},
      "component2": {"name": "ComponentB", "file": "src/module_b/component.py"},
      "similarity": 0.97
    }
  }
]
```

### プロアクティブ提案例
```python
{
  "summary": "アーキテクチャ違反の修正 (src/utils/helper.py)",
  "message": "src/utils/helper.py が禁止されたモジュールに依存しています。修正案を作成しますか？",
  "action_type": "REFACTOR",
  "finding": {
    "type": "DEPENDENCY_VIOLATION",
    "severity": "high",
    "file": "src/utils/helper.py",
    "message": "依存関係違反: ..."
  }
}
```
