# IRGenerator Design Document

## 1. Purpose

`IRGenerator` は `StructuredSpec` を、仕様意味と依存境界を保持した IR ツリーへ変換する。  
runtime 向けの `intent` / `role` だけでなく、`spec_role`, `CHECK` metadata, `RETURN` metadata, `CALCULATE/TRANSFORM/ITERATE/DISPLAY` provenance, `entity_resolution`, structural `input_link` を生成し、後続の `code_synthesis` が保守的に消費できる基盤を作る。

## 2. Structured Specification

### Input
- **Description**: `StructuredSpec` か、`steps` の簡易リスト。任意の `intent_hint` も受け付ける。
- **Type/Format**: `Dict[str, Any] | List[str]`, `Optional[str]`
- **Example**:
  ```json
  {
    "steps": [
      {"id":"step_1","text":"注文一覧を取得する","intent":"FETCH","source_ref":"orders_api","source_kind":"http"}
    ],
    "inputs": [],
    "outputs": [],
    "data_sources": []
  }
  ```

### Output
- **Description**: `logic_tree`, `inputs`, `outputs`, `data_sources` を含む IR。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. リスト入力は `steps` を持つ辞書へ正規化する。
2. `steps` を順に走査し、data source 行と入力説明行を除外する。
3. 必要なら hierarchical clause を抽出し、1 ステップを複数 clause に分割する。
4. 各 clause に対して `_analyze_step_integrated` を実行し、coarse な `intent`, `role`, `cardinality`, `target_entity`, `logic`, `semantic_roles` を得る。
5. 明示 metadata を `semantic_map` に統合し、`source_ref` / `source_kind` の補完を行う。
6. `_resolve_role_specific_semantics` で role-specific enrichment を行う。
   - `spec_role` を付与する。
   - `WRAP/retry` には `wrapper_kind`, `max_attempts`, `exception_type`, `max_attempts_resolution`, `exception_type_resolution`, `retry_delay_policy_resolution` を補完する。
   - explicit `WRAP/timeout` には `wrapper_kind`, `timeout_ms`, `timeout_resolution` を補完する。
   - explicit `WRAP/transaction` には `wrapper_kind`, `transaction_resolution` を補完する。
   - `CHECK` に `check_kind`, `check_subject`, `check_operator`, `check_value`, `expected_truth`, `subject_resolution` を付与する。
    - `TRANSFORM` に `transform_op_resolution`, `transform_source_resolution`, 必要なら `transform_source_node_id` を付与する。
    - `DISPLAY` に schema-backed property がある場合は `property`, `display_property_resolution` を付与する。
   - `ITERATE` に `iteration_source_resolution`, 必要なら `iteration_source_node_id`, `iteration_item_entity`, `iteration_item_resolution`, `iteration_item_var`, `iteration_item_var_resolution` を付与する。
     - explicit `item_entity` がある場合は `iteration_item_resolution=explicit_item_entity` を保持する。
     - explicit `item_var` がある場合は `iteration_item_var_resolution=explicit_item_var` を保持する。
   - `RETURN` に `return_value`, `return_value_resolution`, 必要なら `return_source_node_id` を付与する。
     - structural `input_link` が `CHECK` を指す場合でも、semantic return source はその upstream data node へ引き直す。
   - `FILTER` / `CALCULATE` の昇格と property/provenance 補強を行う。
   - `CALCULATE` では `target_entity`, `entity_resolution`, 必要なら `calculate_source_resolution`, `calculate_source_node_id` を調整する。
7. `_coerce_final_intent_and_role` で runtime intent/role を最終決定する。内部 semantic intent / node kind / runtime role の既定語彙には `src.utils.semantic_intents` の共通定数を使う。
8. `_determine_structural_input_link` で `input_link` を決定する。
   - 構造ブロックの first child は structural parent に接続する。
   - later sibling は直前 sibling を優先する。
   - `ELSE` branch は `CONDITION` を branch base にする。
9. `_build_ir_node` でノードを構築し、構造ツリーへ接続する。
10. 必要なら `JSON_DESERIALIZE` / `JSON_SERIALIZE` bridge node を自動挿入する。
11. context history を更新し、最終 `logic_tree` を返す。
    - `ITERATE` の場合は `iteration_item_entity` / `iteration_item_resolution` に加えて `iteration_item_var` / `iteration_item_var_resolution` も `context history` に残し、nested child の loop-item continuity に使えるようにする。
12. debug 出力は通常経路では行わず、`NLP_DEBUG_STDOUT` が有効な場合のみ補助情報を出す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 1 ステップの `FETCH` を IR ノードへ変換。
  - **Expected Output**: `logic_tree[0].intent == "FETCH"`。
- **Edge Cases**:
  - **Scenario**: `STRICT_SEMANTICS=1` で `ops`/明示意図が無いステップ。
  - **Expected Output / Behavior**: `ValueError` を送出。
  - **Scenario**: `FETCH` の出力型が collection。
  - **Expected Output / Behavior**: `JSON_DESERIALIZE` が挿入される。
  - **Scenario**: `PERSIST` が collection 入力を受ける。
  - **Expected Output / Behavior**: `JSON_SERIALIZE` が挿入される。
  - **Scenario**: `ELSE` 側最初のノード。
  - **Expected Output / Behavior**: then 側ではなく `CONDITION` に接続される。

## 3. Dependencies
- **Internal**:
  - `morph_analyzer`
  - `code_synthesis`
  - `utils`
- **External**: なし

## 4. Notes
- `IRGenerator` は orchestration を維持し、domain-specific logic は helper module へ分割する。
- wrapper metadata の供給は `wrapper_resolution` へ委譲する。
  - `retry`: `max_attempts` は explicit metadata 優先、tokenized `<number> + 回` のみ補完し、それ以外は deterministic default policy metadata (`default_attempts`, `default_exception_type`, `default_no_delay_policy`) として materialize する。
  - `timeout`: explicit `wrapper_kind=timeout` または `timeout_ms/max_duration_ms/duration_ms` がある場合だけ deterministic に扱い、`timeout_ms` と `timeout_resolution` を materialize する。
  - `transaction`: explicit `wrapper_kind=transaction` がある場合だけ deterministic に扱い、`transaction_resolution=explicit_transaction_wrapper` を materialize する。
- literal return metadata の供給は `return_resolution` へ委譲し、quoted literal / `true` / `false` / `null` / numeric literal のみを deterministic に扱う。
- transform provenance の供給は `transform_resolution` へ委譲し、`ops` / `source_var` / structural upstream source だけを deterministic に扱う。
- calculate provenance の供給は `calculate_resolution` へ委譲し、`source_var` / structural upstream source を success path とし、それ以外は `default_scope_var` の weak retention として観測可能に残す。
- iterate provenance の供給は `iterate_resolution` へ委譲し、`source_var`, explicit `item_entity`, explicit `item_var`, structural upstream collection source を deterministic に扱う。
- display property provenance の供給は `display_resolution` へ委譲し、schema-backed exact property / alias match だけを採用する。

## 5. Operational Notes
- clause 解析や role/path の補助トレースは `src.utils.stdout_guard.debug_print` を通す opt-in 出力とする。
- 通常の IR 生成経路では stdout を使わず、正式な結果は返却される IR 構造に限定する。
- 2026-06-04: `IRValidator` / `spec_role_rules` / `promotion_rules` を含む高頻度の internal semantic intent 比較を `src.utils.semantic_intents` へ寄せ、IR 系の内部語彙を対話/action intent から分離した。
