# ActionSynthesizer Design Document

## 1. Purpose

`ActionSynthesizer` は IR ノードを具体的な合成経路へ落とす orchestration 層である。  
特に、`spec_role` を runtime execution intent に橋渡しし、`CHECK`, `FILTER`, `CALCULATE`, `DESERIALIZE`, `RETURN`, `TRANSFORM`, `ITERATE` の metadata-driven dispatch を担う。

## 2. Structured Specification

### Input
- **Description**: 現在ノード、合成 path、任意の future hint、既消費 node ID 集合。
- **Type/Format**: `Dict[str, Any]`, `Dict[str, Any]`, `Optional[str]`, `Optional[set]`

### Output
- **Description**: 更新済み synthesis path 候補群。
- **Type/Format**: `List[Dict[str, Any]]`

### Core Logic
1. ノードから `spec_role` を読み、必要なら execution intent を補正する。
   - `DESERIALIZE` -> `JSON_DESERIALIZE`
   - `FILTER` -> `LINQ`
   - `TRANSFORM` は弱い runtime intent (`GENERAL` / `ACTION`) を `TRANSFORM` に補正する
   - `DISPLAY` は弱い runtime intent を `DISPLAY` に補正する
2. `audit_only` や project ops を先に処理する。
3. action node に明示メソッド ID/名前がある場合は、推定 intent の専用 handler より先にそのメソッドを合成し、非 void 戻り値を後続ノードへ伝播する。
4. `LOOP`, `CONDITION`, `RETURN`, `LINQ`, `CALC`, `DISPLAY/TRANSFORM` は専用 handler へ dispatch する。
  - `RETURN` は `return_value_resolution` がある場合、latest var fallback より前に literal return、explicit `source_var`、または `input_link` 由来の exact upstream var を優先する。
  - `CALCULATE` は `calculate_source_resolution` がある場合、`active_scope_item` や latest var fallback より前に explicit `source_var` または `input_link` 由来の exact upstream var を優先する。
  - `calculate_source_resolution=default_scope_var` は weak retention として扱い、exact upstream node を捏造せず current `active_scope_item` に留める。
  - `TRANSFORM` は `transform_source_resolution` がある場合、`active_scope_item` より前に explicit `source_var` または `input_link` 由来の exact upstream var を優先する。
   - `ITERATE` は `iteration_source_resolution` がある場合、latest collection より前に exact upstream collection を優先する。
   - `ITERATE` は `iteration_item_entity` がある場合、weak collection inner type や `Item` より前にそれを loop item 型として優先する。
   - `iteration_item_var` がある場合は generic `item` ではなくその alias を `foreach` item 名として使う。
   - nested child は上流の `context history.item_entity` により `target_entity` が補強される前提で property binding する。
   - `DISPLAY` child に schema-backed `property` がある場合は `display_transform_ops` 側で `item.<Property>` を優先表示する。
5. `FETCH`, file persist, JSON, IO も専用 handler へ分岐する。
  - plain `env` fetch は `source_kind=env` を保ったまま downstream call synthesis に渡し、`Environment.GetEnvironmentVariable(...)` のような scalar call でも `var_type=string` を落とさない。
  - `Environment.GetEnvironmentVariable(...)` は BCL 上 nullable を返すため、生成される non-null string 変数へ代入する場合は `?? string.Empty` で正規化する。
6. collection 入力で loop 展開が必要な場合は synthetic loop を生成する。
7. 一般アクションは candidate gathering -> 単一メソッド合成で処理する。
8. 候補が無い場合は fallback を試し、それでも無ければ `NotImplementedException` を生成する。
9. `CHECK` / `FILTER` / `CALCULATE` の詳細式や conservatism は binder/handler 側に委譲する。
10. debug 出力は通常経路では行わず、`NLP_DEBUG_STDOUT` が有効な場合のみ candidate gather や unresolved path の補助情報を出す。

### Test Cases
- **Happy Path**:
  - **Scenario**: `spec_role=FILTER` のノード。
  - **Expected Output**: `LINQ` handler に dispatch される。
- **Edge Cases**:
  - **Scenario**: 候補メソッドが無い。
  - **Expected Output / Behavior**: コードを生成せず、対象node IDと解決不能理由を `resolution_errors` に記録する。

## 3. Dependencies
- **Internal**:
  - `semantic_binder`
  - `statement_builder`
  - `action_handlers`
- **External**: なし

## 4. Operational Notes
- candidate gather や unresolved path の補助情報は `src.utils.stdout_guard.debug_print` を使う opt-in 出力とする。
- 通常の synthesis 経路では stdout を使わず、正式な結果は戻り値の synthesis path と generated code に集約する。
- resilient wrap 対象の call に `out_var` がある場合は scalar / collection を問わず explicit `var_type` を保持し、`StatementBuilder.wrap_with_try_catch()` の hoisted declaration が常に妥当な C# 型宣言になるようにする。
- async の `DATABASE_QUERY` / `HTTP_REQUEST` / `PERSIST` call は `StatementBuilder.wrap_with_try_catch()` 側で operation result helper へ変換されるため、`call_expr`、`out_var`、`var_type`、`is_async` を落とさず渡す。
- structured HTTP GET + API key + timeout + `return_default` は raw block ではなく `StatementBuilder.ensure_structured_http_get_string_helper()` の helper call として渡す。caller cancellation や payload 付き HTTP method は既存の raw structured block を維持する。
- loop child path で helper が登録された場合、`extra_code` を親 path へ重複排除して戻す。loop body 内の file persist などが helper call を生成しても、最終 blueprint に helper 定義が残る必要がある。
- condition node に `input_link` があり、その上流ノードが `bool` を生成している場合は、その変数を条件式として優先する。既定 subject を再推論して未定義変数を生成しない。
- 配列コレクションの filter は `ToArray()`、それ以外の collection filter は `ToList()` を使用し、メソッド戻り値型を保存する。

## 5. Review Notes
- 2026-06-29: bool input-link伝播と配列filterの型保存を反映。
- 2026-06-30: 明示メソッド指定を推定 intent より優先し、戻り値を後続引数へ伝播する契約を反映。
- 2026-07-09: env fetch の nullable return を string default へ正規化し、nullable-enabled verification で warning 0 を維持する契約を反映。
- 2026-07-13: async resilient call を operation result helper 化するため、call metadata を保持して `StatementBuilder` に渡す契約を反映。
- 2026-07-13: structured HTTP GET + API key + timeout + `return_default` を helper call に寄せ、複雑な HTTP block を operation method から外す契約を反映。
- 2026-07-13: loop child path の `extra_code` を親 path に戻し、loop 内 helper call の定義欠落を防ぐ契約を反映。
