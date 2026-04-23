# Project Overview (Structure Map)

このプロジェクトは、3つの入口を持つローカルAI基盤として構成されている。モジュールが細分化されているため、入口ごとの処理フローと責務を整理して、全体像を素早く辿れるようにする。

**Entry Points**
- 設計書 → コード生成: `C:\workspace\NLP\scripts\generate\generate_from_design.py`
- 対話パイプライン: `C:\workspace\NLP\src\pipeline_core\pipeline_core.py`
- TDD支援: `C:\workspace\NLP\src\advanced_tdd\main.py`

**Core Flows**
- 設計書生成フロー: Design Parser → IR Generator → Code Synthesis → CodeBuilder
- 対話フロー: Language Analysis → Intent Detection → Semantic Analysis → Task Management → Execution → Response
- TDD支援フロー: Failure Analysis → Fix Suggestion → (Optional) Refactoring Analysis
  - 補足: Code Generation の前に標準 CRUD 仕様の `method_specs` が内部補完される。

**Module Map (By Responsibility)**
- パイプライン入口: `C:\workspace\NLP\src\pipeline_core\pipeline_core.py`
- パイプライン段階定義: `C:\workspace\NLP\src\pipeline_core\stages.py`
- 形態素解析: `C:\workspace\NLP\src\morph_analyzer\morph_analyzer.py`
- 構文解析: `C:\workspace\NLP\src\syntactic_analyzer\syntactic_analyzer.py`
- 意味解析: `C:\workspace\NLP\src\semantic_analyzer\semantic_analyzer.py`
- 意図検出: `C:\workspace\NLP\src\intent_detector\intent_detector.py`
- タスク管理: `C:\workspace\NLP\src\task_manager\task_manager.py`
- 実行系: `C:\workspace\NLP\src\action_executor\action_executor.py`
- 応答生成: `C:\workspace\NLP\src\response_generator\response_generator.py`
- 設計書パーサ: `C:\workspace\NLP\src\design_parser`
- IR生成: `C:\workspace\NLP\src\ir_generator`
- 合成系(コードシンセシス): `C:\workspace\NLP\src\code_synthesis`
- 生成系(コード生成/プロジェクト生成): `C:\workspace\NLP\src\code_generation`
- 検証/監査: `C:\workspace\NLP\src\code_verification`
- ベクトル検索: `C:\workspace\NLP\src\vector_engine`, `C:\workspace\NLP\src\semantic_search`
- TDD支援: `C:\workspace\NLP\src\advanced_tdd`

**Artifacts That Affect Determinism**
- メソッドメタデータ: `C:\workspace\NLP\resources\method_store.json`
- メソッドメタデータ補助: `C:\workspace\NLP\resources\vectors\vector_db\method_store_meta.json`
- メソッドベクトル: `C:\workspace\NLP\resources\vectors\vector_db\method_store_vectors.npy`
- メソッド能力マップ: `C:\workspace\NLP\resources\method_capability_map.json`
- 設計書: `C:\workspace\NLP\scenarios\*.design.md`
- 生成設定: `C:\workspace\NLP\config\config.json`

**Determinism Policy**
- 設計書→コード生成は決定的であることを前提とする
- 対話系は自然さのために非決定性を許容する
- 決定性を最大化する場合は、メタデータとベクトル環境の固定を推奨する
- 補完推論は固定モデル/固定辞書/固定スコアルールに基づく限り許容される
- 外部資産に依存する場合は、パスとバージョンが追跡可能であること

**Traceability Pointers (Design → Code)**
- 入力: `C:\workspace\NLP\scenarios\*.design.md`
- 設計書解析: `C:\workspace\NLP\src\design_parser`
- IR生成: `C:\workspace\NLP\src\ir_generator`
- 合成: `C:\workspace\NLP\src\code_synthesis`
- 出力: `C:\workspace\NLP\cache\*Impact.cs` または `C:\workspace\NLP\{ProjectName}\`
- ブループリント: `C:\workspace\NLP\cache\blueprints\<run_id>\blueprint.json`

**ActionExecutor Action Map (Entry → Execution)**
- コア実行入口: `C:\workspace\NLP\src\action_executor\action_executor.py`
- 学習/知識:
  - `_run_learning_cycle`
  - `_manage_knowledge`
- 辞書/意味検索:
  - `_reverse_dictionary_lookup`
- 設計書生成/補正:
  - `_generate_design_doc`
  - `_refine_design_doc`
- ファイル操作:
  - `_create_file`
  - `_append_file`
  - `_delete_file`
  - `_read_file`
  - `_list_dir`
  - `_move_file`
  - `_copy_file`
- コマンド実行:
  - `_run_command`
- C#解析/テスト:
  - `_analyze_csharp`
  - `_run_dotnet_test`
  - `_parse_dotnet_test_result`
  - `_generate_test_cases`
  - `_load_csharp_analysis_results`
  - `_query_csharp_analysis_results`
- カバレッジ:
  - `_measure_coverage`
  - `_analyze_coverage_gaps`
  - `_generate_coverage_report`
- リファクタリング:
  - `_analyze_refactoring`
  - `_suggest_refactoring`
  - `_apply_refactoring`
- CI/CD:
  - `_setup_cicd_pipeline`
  - `_configure_quality_gates`
  - `_generate_cicd_config`
  - `_check_quality_gates`
- TDD支援:
  - `_analyze_test_failure`
  - `_execute_goal_driven_tdd`
  - `_apply_code_fix`
- 付帯ユーティリティ:
  - `_get_cwd`
  - `_safe_join`
  - `_load_error_patterns`
  - `_handle_exception_with_patterns`
  - `_get_entity_value`
  - `_find_latest_report`
  - `_recursively_find_callers`
  - `_validate_code_syntax`

**Intent → Action Routing (Planner)**
- 参照: `C:\workspace\NLP\src\planner\planner.py`
- FILE_CREATE: `_create_file`
- FILE_READ: `_read_file`
- FILE_APPEND: `_append_file`
- FILE_DELETE: `_delete_file`
- FILE_MOVE: `_move_file`
- FILE_COPY: `_copy_file`
- LIST_DIR: `_list_dir`
- GET_CWD: `_get_cwd`
- CMD_RUN: `_run_command`
- CS_TEST_RUN: `_run_dotnet_test`
- CS_ANALYZE: `_analyze_csharp`
- GENERATE_TESTS: `_generate_test_cases`
- CS_QUERY_ANALYSIS: `_query_csharp_analysis_results`
- CS_IMPACT_SCOPE: `_query_csharp_analysis_results`
- MEASURE_COVERAGE: `_measure_coverage`
- ANALYZE_COVERAGE_GAPS: `_analyze_coverage_gaps`
- GENERATE_COVERAGE_REPORT: `_generate_coverage_report`
- ANALYZE_REFACTORING: `_analyze_refactoring`
- SUGGEST_REFACTORING: `_suggest_refactoring`
- APPLY_REFACTORING: `_apply_refactoring`
- ANALYZE_TEST_FAILURE: `_analyze_test_failure`
- EXECUTE_GOAL_DRIVEN_TDD: `_execute_goal_driven_tdd`
- APPLY_CODE_FIX: `_apply_code_fix`
- RUN_LEARNING_CYCLE: `_run_learning_cycle`
- MANAGE_KNOWLEDGE: `_manage_knowledge`
- REVERSE_DICTIONARY_SEARCH: `_reverse_dictionary_lookup`
- DOC_GEN: `_generate_design_doc`
- DOC_REFINE: `_refine_design_doc`

**Task Definitions (Entry Conditions / Compound Tasks)**
- 定義ファイル: `C:\workspace\NLP\resources\task_definitions.json`
- 単純タスク: FILE_CREATE, FILE_READ, FILE_APPEND, FILE_DELETE, FILE_MOVE, FILE_COPY, LIST_DIR, GET_CWD, CMD_RUN, CS_ANALYZE, CS_TEST_RUN, GENERATE_TESTS, CS_QUERY_ANALYSIS, CS_IMPACT_SCOPE, MEASURE_COVERAGE, ANALYZE_COVERAGE_GAPS, GENERATE_COVERAGE_REPORT, ANALYZE_REFACTORING, SUGGEST_REFACTORING, APPLY_REFACTORING, RUN_LEARNING_CYCLE, MANAGE_KNOWLEDGE, REVERSE_DICTIONARY_SEARCH, DOC_GEN, DOC_REFINE
- 複合タスク: BACKUP_AND_DELETE, READ_AND_CREATE, RECOVERY_FROM_TEST_FAILURE
- 連続フロー型: SETUP_CICD, CONFIGURE_QUALITY_GATES, GENERATE_PIPELINE_CONFIG

**Where To Start (When You Are Lost)**
- 対話処理の入口: `C:\workspace\NLP\src\pipeline_core\pipeline_core.py`
- 設計書生成の入口: `C:\workspace\NLP\scripts\generate\generate_from_design.py`
- プロジェクト生成の入口: `C:\workspace\NLP\src\code_generation\project_generator.py`
- メソッドストア仕様: `C:\workspace\NLP\docs\method_store_spec.md`
