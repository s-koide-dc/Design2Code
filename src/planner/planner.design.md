# Planner Design Document

## 1. Purpose (Updated 2026-04-14)
`Planner` モジュールは、自然言語解析によって得られた意図（Intent）とエンティティを、システムが実行可能な「アクションプラン」に変換します。単なるマッピングにとどまらず、安全ポリシーの検証、タスク状態の管理、リトライ戦略の適用、プロジェクトルールの検証、および依存関係に基づく影響分析を通じたプランの最適化（洗練）を担当します。

**主要機能**:
- **意図からアクションへのマッピング**: Intent を対応する ActionExecutor メソッドに変換（FILE_DELETE は BACKUP_AND_DELETE に切替）
- **プロジェクトルール検証**: 命名規則、ディレクトリ構造の自動チェックと補正
- **Self-Healing機能**: エラー発生時の自動回復プラン生成
- **安全性ポリシー検証**: SafetyPolicyValidatorによる実行前チェック
- **影響分析統合**: コード変更の影響範囲特定とテスト提案
- **タスク状態管理**: 単純タスクと複合タスクの状態遷移管理
- **エンティティ検証**: 必須パラメータの存在確認と信頼度チェック
- **履歴からのエラー検出**: 過去のアクション結果からの自動回復

## 2. Architecture Overview

### 2.1 Core Components

#### Planner (Main Class)
- **役割**: プランニングシステムの中心的なコントローラー
- **責任**:
  - 意図とエンティティの確定
  - プロジェクトルールの適用
  - Self-Healing機能の提供
  - 安全性ポリシーの検証
  - 影響分析の統合
  - プラン生成と最適化

#### Intent-to-Action Mapper
- **役割**: 意図からActionExecutorメソッドへのマッピング
- **責任**:
  - 27種類の意図定義（FILE_CREATE, CS_ANALYZE, GENERATE_TESTS等）
  - メソッド名の解決
  - 必須エンティティの定義取得

#### Project Rule Validator
- **役割**: プロジェクト規約の検証と自動補正
- **責任**:
  - 命名規則チェック（Python: snake_case, C#: PascalCase）
  - ディレクトリ構造の検証
  - 自動補正提案の生成
  - 警告メッセージの生成

#### Self-Healing Engine
- **役割**: エラーからの自動回復プラン生成
- **責任**:
  - AutonomousLearningへの問い合わせ
  - 知識ベースからの修復提案取得
  - リトライルールの適用
  - フォールバックロジックの実行（FileNotFoundError等）

#### Safety Policy Validator
- **役割**: アクションの安全性検証
- **責任**:
  - リスクレベル判定（LOW, MEDIUM, HIGH）
  - ブロック判定（BLOCK）
  - ユーザー承認要求の決定
  - 安全性メッセージの生成

#### Impact Analyzer
- **役割**: コード変更の影響範囲分析
- **責任**:
  - 影響を受けるメソッドの特定
  - 関連テストの検索
  - テスト実行提案の生成
  - 高影響変更の警告

### 2.2 Planning Process

#### Phase 1: Intent and Entity Resolution
1. **タスクタイプ判定**: COMPOUND_TASK vs SIMPLE_TASK
2. **アクティブサブタスク確認**: 複合タスクの場合、現在のサブタスクを取得
3. **意図の確定**: サブタスク名 or 解析結果の意図
4. **エンティティのマージ**: タスクパラメータ + 解析エンティティ
5. **エンティティキーマッピング**: project_path → filename等の調整
6. **デフォルト値設定**: language='csharp'等の自動補完

#### Phase 2: Pre-Planning Checks
1. **DEFINITION意図のバイパス**: 定義要求は即座にリターン
2. **プロジェクトルール検証**: 命名規則、ディレクトリ構造のチェック
3. **自動補正適用**: 違反がある場合、エンティティ値を自動修正
4. **履歴からのエラー検出**: 前回アクション結果の確認
5. **Self-Healing判定**: エラーがある場合、回復プラン生成

#### Phase 3: Intent and Entity Validation
1. **信頼度チェック**: intent_confidence >= threshold
2. **意図の存在確認**: intent in intent_to_action_method
3. **必須エンティティ確認**: required_entities の存在チェック
4. **エンティティ信頼度チェック**: entity_confidence >= threshold
5. **オプションパラメータ追加**: output_path, query等

#### Phase 4: Safety Policy Validation
1. **SafetyPolicyValidator呼び出し**: validate_action
2. **リスクレベル判定**: LOW, MEDIUM, HIGH, BLOCK
3. **承認要求判定**: HIGH RISKの場合、confirmation_needed=True
4. **ブロック処理**: BLOCKの場合、エラー追加してリターン

#### Phase 5: Plan Refinement
1. **影響分析判定**: APPLY_CODE_FIX or CS_IMPACT_SCOPE
2. **影響範囲特定**: _refine_plan_with_impact_analysis
3. **テスト提案生成**: 影響を受けるテストの特定
4. **高影響警告**: 影響メソッド数が3を超える場合

#### Phase 6: Plan Generation
1. **プラン辞書作成**: action_method, parameters, confirmation_needed
2. **安全性情報追加**: safety_check_status, safety_message
3. **親タスク情報追加**: 複合タスクの場合、parent_task
4. **影響分析情報追加**: impacted_methods, suggested_tests
5. **コンテキスト更新**: context['plan']に設定

## 3. Structured Specification

### 3.1 Planner.__init__

#### Input
- **Description**: 初期化パラメータ
- **Type/Format**:
  - `action_executor` (ActionExecutor): アクション実行器インスタンス
  - `log_manager` (LogManager): ログマネージャーインスタンス
  - `autonomous_learning` (AutonomousLearning, optional): 自律学習インスタンス
  - `intent_entity_thresholds` (dict, optional): 信頼度しきい値（intent, entity）
  - `retry_rules_path` (str, optional): リトライルールファイルパス
  - `config_manager` (ConfigManager, optional): 設定マネージャーインスタンス
- **Example**:
  ```python
  planner = Planner(
      action_executor=executor,
      log_manager=log_mgr,
      autonomous_learning=learner,
      intent_entity_thresholds={"intent": 0.8, "entity": 0.8},
      config_manager=config_mgr
  )
  ```

#### Output
- **Description**: Plannerインスタンス
- **Type/Format**: Planner

#### Core Logic
1. **基本設定**:
   - `self.action_executor = action_executor`
   - `self.log_manager = log_manager`
   - `self.autonomous_learning = autonomous_learning`
   - `self.config_manager = config_manager`

2. **しきい値設定**:
   - `self.intent_threshold = intent_entity_thresholds.get("intent", 0.8)`
   - `self.entity_threshold = intent_entity_thresholds.get("entity", 0.8)`

3. **リトライルール読み込み**:
   - `config_manager`が存在する場合: `config_manager.get_retry_rules()`
   - 存在しない場合: `_load_retry_rules(retry_rules_path or "resources/retry_rules.json")`

4. **SafetyPolicyValidator初期化**:
   - `self.safety_validator = SafetyPolicyValidator(action_executor, config_manager=config_manager)`

5. **意図マッピング定義**:
   - `self.intent_to_action_method`辞書を作成
   - 27種類の意図をActionExecutorメソッドにマッピング:
     - FILE_CREATE → _create_file
     - FILE_READ → _read_file
     - FILE_APPEND → _append_file
     - FILE_DELETE → _delete_file
     - FILE_MOVE → _move_file
     - FILE_COPY → _copy_file
     - LIST_DIR → _list_dir
     - GET_CWD → _get_cwd
     - CMD_RUN → _run_command
     - CS_TEST_RUN → _run_dotnet_test
     - CS_ANALYZE → _analyze_csharp
     - GENERATE_TESTS → _generate_test_cases
     - CS_QUERY_ANALYSIS → _query_csharp_analysis_results
     - CS_IMPACT_SCOPE → _query_csharp_analysis_results
     - MEASURE_COVERAGE → _measure_coverage
     - ANALYZE_COVERAGE_GAPS → _analyze_coverage_gaps
     - GENERATE_COVERAGE_REPORT → _generate_coverage_report
     - ANALYZE_REFACTORING → _analyze_refactoring
     - SUGGEST_REFACTORING → _suggest_refactoring
     - APPLY_REFACTORING → _apply_refactoring
     - ANALYZE_TEST_FAILURE → _analyze_test_failure
     - APPLY_CODE_FIX → _apply_code_fix
     - RUN_LEARNING_CYCLE → _run_learning_cycle
     - MANAGE_KNOWLEDGE → _manage_knowledge
  - DOC_GEN → _generate_design_doc
  - DOC_REFINE → _refine_design_doc
  - REVERSE_DICTIONARY_SEARCH → _reverse_dictionary_lookup
  - EXECUTE_GOAL_DRIVEN_TDD → _execute_goal_driven_tdd

### 3.2 Planner.create_plan

#### Input
- **Description**: プラン生成のためのコンテキスト
- **Type/Format**: dict
- **Example**:
  ```json
  {
    "session_id": "session_123",
    "original_text": "ファイルを作成してください",
    "analysis": {
      "intent": "FILE_CREATE",
      "intent_confidence": 0.95,
      "entities": {
        "filename": {"value": "test.py", "confidence": 0.9}
      }
    },
    "task": {
      "type": "SIMPLE_TASK",
      "name": "FILE_CREATE",
      "state": "READY_FOR_EXECUTION",
      "parameters": {}
    },
    "history": [],
    "errors": []
  }
  ```

#### Output
- **Description**: プランを含むコンテキスト
- **Type/Format**: dict
- **Example**:
  ```json
  {
    "plan": {
      "action_method": "_create_file",
      "parameters": {"filename": "test.py"},
      "confirmation_needed": false,
      "safety_check_status": "OK",
      "safety_message": "Action is safe to execute"
    }
  }
  ```

#### Core Logic
1. **初期化**:
   - `context.setdefault("errors", [])`
   - ログイベント記録: `planner_create_plan_start`

2. **履歴からのエラー検出**:
   - `previous_action_result = context.get("action_result", {})`
   - 空の場合、`history`の最後のエントリを確認
   - `status == "error"`の場合、`previous_action_result`に設定

3. **既存エラーチェック**:
   - `context.get("errors")`が存在する場合、即座にリターン

4. **タスク情報取得**:
   - `current_task = context.get("task", {})`
   - `task_type = current_task.get("type", "SIMPLE_TASK")`
   - `task_state = current_task.get("state")`

5. **意図とエンティティの確定**:
   - **複合タスクの場合**:
     - `sub_task_index = current_task.get("current_subtask_index", 0)`
     - `active_subtask = current_task["subtasks"][sub_task_index]`
     - `intent = active_subtask["name"]`
     - `entities = active_subtask.get("parameters", {})`
     - `intent_confidence = 1.0`（サブタスクは確定）
   - **単純タスクの場合**:
     - タスク状態が`READY_FOR_EXECUTION`の場合: `intent = current_task["name"]`
     - それ以外: `intent = context["analysis"].get("intent")`
     - `intent_confidence = context["analysis"].get("intent_confidence", 0.0)`
     - エンティティのマージ: `task_parameters` + `analysis_entities`

6. **エンティティキーマッピング**:
   - `CS_ANALYZE`意図で`project_path`が存在し`filename`が存在しない場合:
     - `merged_entities["filename"] = merged_entities["project_path"]`
   - プロジェクト分析意図（MEASURE_COVERAGE等）で`language`が存在しない場合:
     - `merged_entities["language"] = {"value": "csharp", "confidence": 1.0}`

7. **DEFINITION意図のバイパス**:
   - `intent == "DEFINITION"`の場合、即座にリターン

8. **プロジェクトルール検証**:
   - `_apply_project_rules(intent, raw_params_for_validation)`を呼び出し
   - 警告がある場合、ログ記録
   - 自動補正提案がある場合、エンティティ値を更新

9. **Self-Healing判定**:
   - `previous_action_result.get("status") == "error"`の場合:
     - `_plan_self_healing(context, previous_action_result)`を呼び出し
     - 回復プランが見つかった場合、`context["plan"]`に設定してリターン
     - 見つからない場合、リトライルールを確認
     - マッチするルールがある場合、リトライ提案を生成してリターン

10. **意図と信頼度の検証**:
    - タスクが`READY_FOR_EXECUTION`でない場合:
      - `intent_confidence < self.intent_threshold`の場合、エラー追加してリターン
    - `intent`が存在しないか`intent_to_action_method`に存在しない場合、エラー追加してリターン

11. **必須エンティティの検証**:
    - `action_method_name = self.intent_to_action_method.get(intent)`
    - `intent == "FILE_DELETE"` の場合は `BACKUP_AND_DELETE` の action_method を優先
    - `required_entities = self.action_executor.get_required_entities_for_intent(intent)`
    - 各必須エンティティに対して:
      - 存在確認
      - 値の存在確認
      - 信頼度確認（`>= self.entity_threshold`）
    - 不足エンティティがある場合、エラー追加してリターン
    - 低信頼度エンティティがある場合、エラー追加してリターン

12. **オプションパラメータ追加**:
    - `output_path`, `query`が存在する場合、`plan_parameters`に追加

13. **CS_IMPACT_SCOPE特別処理**:
    - `query_type = "impact_scope_method"`を設定
    - `target_name`が存在する場合、`plan_parameters`に追加

14. **安全性ポリシー検証**:
    - `safety_result = self.safety_validator.validate_action(action_method_name, plan_parameters, intent)`
    - `risk_level == RiskLevel.HIGH`かつ複合タスク実行中でない場合:
      - `confirmation_needed = True`
    - `status == SafetyCheckStatus.BLOCK`の場合:
      - エラー追加してリターン

15. **プラン生成**:
    - `context["plan"]`辞書を作成:
      - `action_method`: アクションメソッド名
      - `parameters`: パラメータ辞書
      - `confirmation_needed`: 承認要求フラグ
      - `safety_check_status`: 安全性チェック結果
      - `safety_message`: 安全性メッセージ
    - 複合タスクの場合、`parent_task`を追加

16. **影響分析統合**:
    - `intent in ["APPLY_CODE_FIX", "CS_IMPACT_SCOPE"]`かつ`output_path`が存在する場合:
      - `_refine_plan_with_impact_analysis(context, plan_parameters)`を呼び出し

17. **ログ記録とリターン**:
    - ログイベント記録: `planner_plan_created`
    - `context`を返却

### 3.3 Planner._apply_project_rules

#### Input
- **Description**: プロジェクトルール検証のためのパラメータ
- **Type/Format**:
  - `intent` (str): 意図名
  - `parameters` (dict): パラメータ辞書
- **Example**:
  ```python
  _apply_project_rules("FILE_CREATE", {"filename": "TestFile.py"})
  ```

#### Output
- **Description**: 警告と自動補正提案
- **Type/Format**: dict
- **Example**:
  ```json
  {
    "warnings": ["Filename 'TestFile.py' violates Python naming convention (snake_case required)."],
    "adjustments": {"suggested_filename": "test_file.py"}
  }
  ```

#### Core Logic
1. **プロジェクトルール読み込み**:
   - `rules = self._load_project_rules()`
   - ルールが存在しない場合、空辞書を返却

2. **初期化**:
   - `warnings = []`
   - `adjustments = {}`

3. **命名規則チェック（ファイル作成/移動/コピー）**:
   - `intent in ["FILE_CREATE", "FILE_MOVE", "FILE_COPY"]`の場合:
     - `filename = parameters.get("filename") or parameters.get("destination_filename")`
     - `basename = os.path.basename(filename)`
     - `naming = rules.get("naming_conventions", {}).get("files", {})`

4. **Python snake_caseチェック**:
   - `filename.endswith(".py")`の場合:
     - 大文字が含まれているか確認
     - 含まれている場合:
       - 警告メッセージを追加
       - 正規表現で`snake_case`に変換: `re.sub(r'(?<!^)(?=[A-Z])', '_', basename).lower()`
       - `adjustments["suggested_filename"]`に設定

5. **C# PascalCaseチェック**:
   - `filename.endswith(".cs")`の場合:
     - 最初の文字が小文字か確認
     - 小文字の場合:
       - 警告メッセージを追加
       - 最初の文字を大文字に変換
       - `adjustments["suggested_filename"]`に設定

6. **結果返却**:
   - `{"warnings": warnings, "adjustments": adjustments}`を返却

### 3.4 Planner._plan_self_healing

#### Input
- **Description**: エラー情報を含むコンテキスト
- **Type/Format**:
  - `context` (dict): コンテキスト辞書
  - `error_result` (dict): エラー結果辞書
- **Example**:
  ```json
  {
    "original_error_type": "FileNotFoundError",
    "message": "No such file or directory: 'test.py'"
  }
  ```

#### Output
- **Description**: 回復プラン（見つからない場合はNone）
- **Type/Format**: dict or None
- **Example**:
  ```json
  {
    "action_method": "_list_dir",
    "parameters": {"directory": "."},
    "suggestion": "ファイル 'test.py' が見つかりませんでした。ディレクトリの一覧を確認して、正しいファイルを探しますか？",
    "confirmation_needed": true,
    "healing_type": "FILE_NOT_FOUND_RECOVERY"
  }
  ```

#### Core Logic
1. **エラー情報抽出**:
   - `error_type = error_result.get("original_error_type") or error_result.get("error_type")`
   - `error_msg = error_result.get("original_error", "") or error_result.get("message", "")`

2. **AutonomousLearning問い合わせ**:
   - `self.autonomous_learning`が存在する場合:
     - `suggestion = self.autonomous_learning.get_repair_suggestion(error_result)`
     - 提案が見つかった場合:
       - `action`を確認
       - `ANALYZE_TEST_FAILURE`の場合:
         - 回復プラン辞書を作成（action_method, parameters, suggestion, evidence, confirmation_needed, healing_type）
         - 返却
       - `RETRY_WITH_ADJUSTMENT`の場合:
         - リトライ提案辞書を作成（suggestion, evidence, retry_possible, proposed_adjustments, healing_type）
         - 返却

3. **FileNotFoundErrorシナリオ**:
   - `error_type == "FileNotFoundError"`または`"No such file" in error_msg`または`"見つかりません" in error_msg`の場合:
     - 正規表現でファイル名を抽出: `r"'(.*?)'"`
     - 日本語引用符も試行: `r"ファイル '(.*?)'"`
     - ファイル名が見つからない場合、`context["analysis"]["entities"]["filename"]["value"]`を使用
     - ファイル名が見つかった場合:
       - ログイベント記録: `planner_self_healing_file_not_found`
       - 回復プラン辞書を作成:
         - `action_method = "_list_dir"`
         - `parameters = {"directory": os.path.dirname(filename) or "."}`
         - `suggestion`: ディレクトリ一覧確認の提案
         - `confirmation_needed = True`
         - `healing_type = "FILE_NOT_FOUND_RECOVERY"`
       - 返却

4. **C#ビルドエラーシナリオ**:
   - `"CS" in error_msg`かつ`error_type == "subprocess.CalledProcessError"`の場合:
     - 将来的な拡張ポイント（現在はパススルー）

5. **結果返却**:
   - 回復プランが見つからない場合、`None`を返却

### 3.5 Planner._refine_plan_with_impact_analysis

#### Input
- **Description**: 影響分析のためのコンテキストとパラメータ
- **Type/Format**:
  - `context` (dict): コンテキスト辞書
  - `parameters` (dict): パラメータ辞書
- **Example**:
  ```json
  {
    "output_path": "cache/analysis_output/project_analysis.json",
    "target_name": "MyClass.MyMethod"
  }
  ```

#### Output
- **Description**: なし（contextを直接更新）
- **Type/Format**: None

#### Core Logic
1. **パラメータ抽出**:
   - `output_path = parameters.get("output_path")`
   - `target_name = parameters.get("target_name")`

2. **履歴からの回復**:
   - `output_path`または`target_name`が存在しない場合:
     - `history = context.get("history", [])`を逆順で走査
     - 過去のエンティティから`target_name`と`output_path`を取得
     - 両方見つかったら終了

3. **必須パラメータチェック**:
   - `output_path`または`target_name`が存在しない場合、即座にリターン

4. **ログ記録**:
   - ログイベント記録: `planner_impact_analysis_start`

5. **影響範囲クエリ**:
   - `query_params`辞書を作成:
     - `output_path`: 解析結果ファイルパス
     - `query_type`: "impact_scope_method"
     - `target_name`: ターゲットメソッド名
   - 一時コンテキストを作成
   - `self.action_executor._query_csharp_analysis_results(temp_context, query_params)`を呼び出し

6. **影響メソッドの処理**:
   - クエリ結果が成功の場合:
     - `impacted_methods = query_result_context["action_result"].get("impacted_methods", [])`
     - 影響メソッドが存在する場合:
       - `context["plan"]["impacted_methods"]`に設定
       - ログイベント記録: `planner_impact_detected`

7. **関連テストの検索**:
   - 影響メソッドが存在する場合:
     - `test_query_params`辞書を作成:
       - `output_path`: 解析結果ファイルパス
       - `query_type`: "find_tests_for_methods"
       - `target_name`: 影響メソッドのカンマ区切りリスト
     - `self.action_executor._query_csharp_analysis_results(temp_context, test_query_params)`を呼び出し

8. **テスト自体の影響チェック**:
   - 影響メソッドに"Test"が含まれる場合:
     - `associated_tests`に追加（重複チェック）

9. **テスト提案の生成**:
   - 関連テストが存在する場合:
     - `context["plan"]["suggested_tests"]`に設定
     - テストファイル名を抽出（"Unknown"を除外）
     - ファイル名が存在しない場合、クラス名を使用
     - `context["plan"]["suggestion"]`に提案メッセージを設定
     - `context["plan"]["confirmation_needed"] = True`

10. **高影響警告**:
    - 影響メソッド数が3を超え、テスト提案が存在しない場合:
      - `context["plan"]["suggestion"]`に高影響警告メッセージを設定
      - `context["plan"]["confirmation_needed"] = True`

11. **例外処理**:
    - すべての処理を`try-except`で囲む
    - エラー時: ログイベント記録（`planner_impact_analysis_error`）

### 3.6 Planner._load_retry_rules

#### Input
- **Description**: リトライルールファイルパス
- **Type/Format**: str
- **Example**: `"resources/retry_rules.json"`

#### Output
- **Description**: リトライルールリスト
- **Type/Format**: list
- **Example**:
  ```json
  [
    {
      "error_type": "FileNotFoundError",
      "max_retries": 3,
      "backoff_seconds": 2
    }
  ]
  ```

#### Core Logic
1. **ファイル存在確認**:
   - `os.path.exists(filepath)`が`False`の場合、空リストを返却

2. **ファイル読み込み**:
   - `try-except`ブロックで囲む
   - `open(filepath, 'r', encoding='utf-8')`でファイルを開く
   - `json.load(f).get("retry_rules", [])`でルールリストを取得

3. **例外処理**:
   - 例外が発生した場合、空リストを返却

4. **結果返却**:
   - ルールリストを返却

### 3.7 Planner._load_project_rules

#### Input
- **Description**: なし
- **Type/Format**: None

#### Output
- **Description**: プロジェクトルール辞書
- **Type/Format**: dict
- **Example**:
  ```json
  {
    "naming_conventions": {
      "files": {
        "python": "snake_case",
        "csharp": "PascalCase"
      }
    }
  }
  ```

#### Core Logic
1. **ファイルパス構築**:
   - `rule_path = os.path.join("resources", "project_rules.json")`

2. **ファイル存在確認**:
   - `os.path.exists(rule_path)`が`False`の場合、空辞書を返却

3. **ファイル読み込み**:
   - `try-except`ブロックで囲む
   - `open(rule_path, 'r', encoding='utf-8')`でファイルを開く
   - `json.load(f)`でルール辞書を取得

4. **例外処理**:
   - 例外が発生した場合、空辞書を返却

5. **結果返却**:
   - ルール辞書を返却

## 4. Consumers
- **pipeline_core**: メインパイプラインからのプラン生成要求
- **task_manager**: タスク実行前のプラン検証
- **action_executor**: アクション実行前の安全性確認
- **test_generator**: テスト生成時のプラン作成

## 5. Dependencies

### Internal Dependencies
- **action_executor**: アクション実行器（メソッド名解決、必須エンティティ取得、C#解析結果クエリ）
- **log_manager**: イベントログの記録
- **autonomous_learning**: 修復提案の取得（`get_repair_suggestion`）
- **safety_policy_validator**: 安全性ポリシーの検証
- **config_manager**: 設定の取得（リトライルール等）

### External Dependencies
- **os**: ファイルシステム操作（パス操作、ファイル存在確認）
- **json**: 設定ファイル、ルールファイルの読み込み
- **re**: 正規表現マッチング（ファイル名抽出、命名規則変換）

## 6. Configuration

### 6.1 Configuration Parameters
- **intent_entity_thresholds**: 信頼度しきい値
  - `intent` (float): 意図の最小信頼度（デフォルト: 0.8）
  - `entity` (float): エンティティの最小信頼度（デフォルト: 0.8）

### 6.2 Retry Rules File
- **Path**: `resources/retry_rules.json`
- **Format**: JSON
- **Structure**:
  ```json
  {
    "retry_rules": [
      {
        "error_type": "FileNotFoundError",
        "max_retries": 3,
        "backoff_seconds": 2,
        "message_pattern": "No such file"
      }
    ]
  }
  ```

### 6.3 Project Rules File
- **Path**: `resources/project_rules.json`
- **Format**: JSON
- **Structure**:
  ```json
  {
    "naming_conventions": {
      "files": {
        "python": "snake_case",
        "csharp": "PascalCase"
      },
      "directories": {
        "src": "snake_case",
        "tests": "snake_case"
      }
    },
    "directory_structure": {
      "src": ["required"],
      "tests": ["required"],
      "docs": ["optional"]
    }
  }
  ```

### 6.4 Intent-to-Action Mapping
- **FILE_CREATE**: ファイル作成
- **FILE_READ**: ファイル読み込み
- **FILE_APPEND**: ファイル追記
- **FILE_DELETE**: ファイル削除
- **FILE_MOVE**: ファイル移動
- **FILE_COPY**: ファイルコピー
- **LIST_DIR**: ディレクトリ一覧
- **GET_CWD**: 現在のディレクトリ取得
- **CMD_RUN**: コマンド実行
- **CS_TEST_RUN**: C#テスト実行
- **CS_ANALYZE**: C#静的解析
- **GENERATE_TESTS**: テスト生成
- **CS_QUERY_ANALYSIS**: C#解析結果クエリ
- **CS_IMPACT_SCOPE**: 影響範囲クエリ
- **MEASURE_COVERAGE**: カバレッジ測定
- **ANALYZE_COVERAGE_GAPS**: カバレッジギャップ分析
- **GENERATE_COVERAGE_REPORT**: カバレッジレポート生成
- **ANALYZE_REFACTORING**: リファクタリング分析
- **SUGGEST_REFACTORING**: リファクタリング提案
- **APPLY_REFACTORING**: リファクタリング適用
- **ANALYZE_TEST_FAILURE**: テスト失敗分析
- **APPLY_CODE_FIX**: コード修正適用
- **RUN_LEARNING_CYCLE**: 学習サイクル実行
- **MANAGE_KNOWLEDGE**: 知識管理
- **DOC_GEN**: 設計書生成
- **DOC_REFINE**: 設計書補完
- **REVERSE_DICTIONARY_SEARCH**: 逆引き検索
- **EXECUTE_GOAL_DRIVEN_TDD**: 目標駆動TDD実行

## 7. Integration Workflow

### 7.1 Standard Planning Flow
1. **Pipeline Core**: `create_plan(context)`を呼び出し
2. **Planner**: 意図とエンティティを確定
3. **Planner**: プロジェクトルールを検証
4. **Planner**: 必須エンティティを確認
5. **SafetyPolicyValidator**: 安全性を検証
6. **Planner**: プランを生成
7. **Pipeline Core**: プランを受け取り、ActionExecutorに渡す

### 7.2 Self-Healing Flow
1. **Pipeline Core**: エラーを含むコンテキストで`create_plan`を呼び出し
2. **Planner**: 履歴からエラーを検出
3. **Planner**: `_plan_self_healing`を呼び出し
4. **AutonomousLearning**: `get_repair_suggestion`で修復提案を取得
5. **Planner**: 回復プランを生成
6. **Pipeline Core**: 回復プランを受け取り、実行

### 7.3 Impact Analysis Flow
1. **Planner**: `APPLY_CODE_FIX`または`CS_IMPACT_SCOPE`意図を検出
2. **Planner**: `_refine_plan_with_impact_analysis`を呼び出し
3. **ActionExecutor**: C#解析結果から影響範囲を取得
4. **ActionExecutor**: 関連テストを検索
5. **Planner**: 影響情報とテスト提案をプランに追加
6. **Pipeline Core**: 拡張されたプランを受け取り、ユーザーに提示

### 7.4 Project Rule Validation Flow
1. **Planner**: ファイル作成/移動/コピー意図を検出
2. **Planner**: `_apply_project_rules`を呼び出し
3. **Planner**: 命名規則をチェック
4. **Planner**: 違反がある場合、自動補正を提案
5. **Planner**: エンティティ値を更新
6. **LogManager**: 警告と補正をログ記録

## 8. Error Handling

### 8.1 Low Intent Confidence
- **Scenario**: 意図の信頼度がしきい値未満
- **Detection**: `intent_confidence < self.intent_threshold`
- **Response**: エラーメッセージを`context["errors"]`に追加、ログ記録、リターン

### 8.2 Unknown Intent
- **Scenario**: 意図が`intent_to_action_method`に存在しない
- **Detection**: `intent not in self.intent_to_action_method`
- **Response**: エラーメッセージを`context["errors"]`に追加、ログ記録、リターン

### 8.3 Missing Required Entities
- **Scenario**: 必須エンティティが不足
- **Detection**: `required_entities`の存在確認
- **Response**: エラーメッセージを`context["errors"]`に追加、ログ記録、リターン

### 8.4 Low Entity Confidence
- **Scenario**: エンティティの信頼度がしきい値未満
- **Detection**: `entity_confidence < self.entity_threshold`
- **Response**: エラーメッセージを`context["errors"]`に追加、ログ記録、リターン

### 8.5 Safety Policy Block
- **Scenario**: 安全性ポリシーによるブロック
- **Detection**: `safety_result.status == SafetyCheckStatus.BLOCK`
- **Response**: エラーメッセージを`context["errors"]`に追加、ログ記録、リターン

### 8.6 Impact Analysis Failure
- **Scenario**: 影響分析中の例外
- **Detection**: `try-except`ブロック
- **Response**: 警告ログ記録、処理継続（影響分析なしでプラン生成）

### 8.7 File Loading Errors
- **Scenario**: リトライルールまたはプロジェクトルールの読み込み失敗
- **Detection**: ファイルI/O例外
- **Response**: 空リスト/空辞書を返却、処理継続

## 9. Performance Considerations

### 9.1 Entity Validation Optimization
- **Issue**: 大量のエンティティ検証
- **Solution**: 
  - 必須エンティティのみを検証
  - 早期リターン（最初の不足で即座に終了）
  - オプションパラメータは後で追加

### 9.2 Impact Analysis Caching
- **Issue**: 頻繁なC#解析結果クエリ
- **Solution**:
  - ActionExecutor側でのキャッシング
  - 一時コンテキストの使用
  - 必要な場合のみ実行

### 9.3 Rule Loading Optimization
- **Issue**: 毎回のルールファイル読み込み
- **Solution**:
  - ConfigManager経由での読み込み（キャッシング）
  - ファイル存在確認の早期実行
  - 空リスト/空辞書の即座返却

### 9.4 Self-Healing Priority
- **Issue**: 複数の回復戦略の評価
- **Solution**:
  - AutonomousLearning優先（学習済み知識）
  - リトライルール次点（設定ベース）
  - フォールバックロジック最後（ハードコード）
  - 最初にマッチした戦略で即座にリターン

## 10. Future Enhancements

### 10.1 Advanced Project Rule Validation
- **Current**: 基本的な命名規則チェック
- **Enhancement**:
  - ディレクトリ構造の検証
  - ファイルサイズ制限
  - 依存関係の検証
  - カスタムルールの動的追加

### 10.2 Machine Learning-Based Planning
- **Current**: ルールベースのプランニング
- **Enhancement**:
  - 過去の成功パターンからの学習
  - コンテキストに応じた最適プラン選択
  - ユーザー嗜好の学習

### 10.3 Multi-Step Plan Generation
- **Current**: 単一アクションプラン
- **Enhancement**:
  - 複数ステップの自動プラン生成
  - 依存関係の自動解決
  - 並列実行可能なアクションの特定

### 10.4 Advanced Impact Analysis
- **Current**: C#メソッドレベルの影響分析
- **Enhancement**:
  - クロスモジュール影響分析
  - パフォーマンス影響の予測
  - セキュリティ影響の評価
  - データフロー分析

### 10.5 Proactive Planning
- **Current**: リアクティブなプラン生成
- **Enhancement**:
  - 潜在的な問題の事前検出
  - 予防的なアクション提案
  - リスク評価に基づく代替プラン生成

## 11. Test Cases

### TC1: Happy Path - File Create
- **Scenario**: ファイル作成の基本プラン生成
- **Input**:
  ```json
  {
    "analysis": {
      "intent": "FILE_CREATE",
      "intent_confidence": 0.95,
      "entities": {
        "filename": {"value": "test.py", "confidence": 0.9}
      }
    }
  }
  ```
- **Expected Output**:
  ```json
  {
    "plan": {
      "action_method": "_create_file",
      "parameters": {"filename": "test.py"},
      "confirmation_needed": false,
      "safety_check_status": "OK"
    }
  }
  ```

### TC2: Project Rule Violation - Python Naming
- **Scenario**: Python命名規則違反の自動補正
- **Input**:
  ```json
  {
    "analysis": {
      "intent": "FILE_CREATE",
      "intent_confidence": 0.95,
      "entities": {
        "filename": {"value": "TestFile.py", "confidence": 0.9}
      }
    }
  }
  ```
- **Expected Output**:
  - 警告ログ記録: "Filename 'TestFile.py' violates Python naming convention"
  - エンティティ値が"test_file.py"に自動補正
  - プラン生成: `{"filename": "test_file.py"}`

### TC3: Self-Healing - FileNotFoundError
- **Scenario**: ファイル未検出エラーからの自動回復
- **Input**:
  ```json
  {
    "action_result": {
      "status": "error",
      "original_error_type": "FileNotFoundError",
      "message": "No such file or directory: 'test.py'"
    }
  }
  ```
- **Expected Output**:
  ```json
  {
    "plan": {
      "action_method": "_list_dir",
      "parameters": {"directory": "."},
      "suggestion": "ファイル 'test.py' が見つかりませんでした。ディレクトリの一覧を確認して、正しいファイルを探しますか？",
      "confirmation_needed": true,
      "healing_type": "FILE_NOT_FOUND_RECOVERY"
    }
  }
  ```

### TC4: Self-Healing - AutonomousLearning Suggestion
- **Scenario**: 学習済み修復パターンの適用
- **Input**:
  ```json
  {
    "action_result": {
      "status": "error",
      "original_error_type": "CompilationError",
      "message": "CS0103: The name does not exist"
    }
  }
  ```
- **Expected Output**:
  - AutonomousLearning.get_repair_suggestionが呼び出される
  - 修復提案が返される（action="ANALYZE_TEST_FAILURE"）
  - プランに`evidence`フィールドが含まれる

### TC5: Low Intent Confidence
- **Scenario**: 意図の信頼度不足
- **Input**:
  ```json
  {
    "analysis": {
      "intent": "FILE_CREATE",
      "intent_confidence": 0.5,
      "entities": {
        "filename": {"value": "test.py", "confidence": 0.9}
      }
    }
  }
  ```
- **Expected Output**:
  - エラーメッセージ: "意図の信頼度が低すぎます: FILE_CREATE (信頼度: 0.50)"
  - `context["errors"]`にエラーが追加される
  - プランが生成されない

### TC6: Missing Required Entity
- **Scenario**: 必須エンティティの不足
- **Input**:
  ```json
  {
    "analysis": {
      "intent": "FILE_CREATE",
      "intent_confidence": 0.95,
      "entities": {}
    }
  }
  ```
- **Expected Output**:
  - エラーメッセージ: "必須エンティティが不足しています: filename"
  - `context["errors"]`にエラーが追加される
  - プランが生成されない

### TC7: Safety Policy Block
- **Scenario**: 安全性ポリシーによるブロック
- **Input**:
  ```json
  {
    "analysis": {
      "intent": "CMD_RUN",
      "intent_confidence": 0.95,
      "entities": {
        "command": {"value": "rm -rf /", "confidence": 0.9}
      }
    }
  }
  ```
- **Expected Output**:
  - SafetyPolicyValidator.validate_actionが呼び出される
  - `status == SafetyCheckStatus.BLOCK`
  - エラーメッセージ: "Safety Policy Error: ..."
  - `context["errors"]`にエラーが追加される

### TC8: High Risk Confirmation
- **Scenario**: 高リスクアクションの承認要求
- **Input**:
  ```json
  {
    "analysis": {
      "intent": "FILE_DELETE",
      "intent_confidence": 0.95,
      "entities": {
        "filename": {"value": "important.py", "confidence": 0.9}
      }
    }
  }
  ```
- **Expected Output**:
  - SafetyPolicyValidator.validate_actionが呼び出される
  - `risk_level == RiskLevel.HIGH`
  - プラン生成: `{"confirmation_needed": true}`

### TC9: Impact Analysis - Code Fix
- **Scenario**: コード修正時の影響分析
- **Input**:
  ```json
  {
    "analysis": {
      "intent": "APPLY_CODE_FIX",
      "intent_confidence": 0.95,
      "entities": {
        "output_path": {"value": "cache/analysis_output/project.json", "confidence": 1.0},
        "target_name": {"value": "MyClass.MyMethod", "confidence": 0.9}
      }
    }
  }
  ```
- **Expected Output**:
  - `_refine_plan_with_impact_analysis`が呼び出される
  - ActionExecutor._query_csharp_analysis_resultsが呼び出される（2回）
  - プランに`impacted_methods`が追加される
  - プランに`suggested_tests`が追加される
  - プランに`suggestion`が追加される

### TC10: Compound Task - Subtask Planning
- **Scenario**: 複合タスクのサブタスクプラン生成
- **Input**:
  ```json
  {
    "task": {
      "type": "COMPOUND_TASK",
      "name": "MULTI_FILE_OPERATION",
      "state": "IN_PROGRESS",
      "current_subtask_index": 0,
      "subtasks": [
        {
          "name": "FILE_CREATE",
          "parameters": {
            "filename": {"value": "test1.py", "confidence": 1.0}
          }
        }
      ]
    }
  }
  ```
- **Expected Output**:
  - サブタスクの意図が使用される（FILE_CREATE）
  - `intent_confidence = 1.0`（サブタスクは確定）
  - プラン生成: `{"action_method": "_create_file", "parent_task": "MULTI_FILE_OPERATION"}`

### TC11: Entity Key Mapping - CS_ANALYZE
- **Scenario**: project_pathからfilenameへの自動マッピング
- **Input**:
  ```json
  {
    "analysis": {
      "intent": "CS_ANALYZE",
      "intent_confidence": 0.95,
      "entities": {
        "project_path": {"value": "MyProject.csproj", "confidence": 0.9}
      }
    }
  }
  ```
- **Expected Output**:
  - `merged_entities["filename"] = "MyProject.csproj"`
  - プラン生成: `{"parameters": {"filename": "MyProject.csproj"}}`

### TC12: History-Based Error Detection
- **Scenario**: 履歴からのエラー検出と回復
- **Input**:
  ```json
  {
    "history": [
      {
        "action_result": {
          "status": "error",
          "original_error_type": "FileNotFoundError",
          "message": "No such file: 'test.py'"
        }
      }
    ]
  }
  ```
- **Expected Output**:
  - `previous_action_result`が履歴から取得される
  - `_plan_self_healing`が呼び出される
  - 回復プランが生成される
