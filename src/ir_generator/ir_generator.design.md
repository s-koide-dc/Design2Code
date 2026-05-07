# IRGenerator Design Document

## 1. Purpose

`IRGenerator` は `StructuredSpec` を、仕様意味と依存境界を保持した IR ツリーへ変換する。  
runtime 向けの `intent` / `role` だけでなく、`spec_role`, `CHECK` metadata, provenance, `entity_resolution`, structural `input_link` を生成し、後続の `code_synthesis` が保守的に消費できる基盤を作る。

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
   - `CHECK` に `check_kind`, `check_subject`, `check_operator`, `check_value`, `expected_truth`, `subject_resolution` を付与する。
   - `FILTER` / `CALCULATE` の昇格と property/provenance 補強を行う。
   - `CALCULATE` では `target_entity` と `entity_resolution` を調整する。
7. `_coerce_final_intent_and_role` で runtime intent/role を最終決定する。
8. `_determine_structural_input_link` で `input_link` を決定する。
   - 構造ブロックの first child は structural parent に接続する。
   - later sibling は直前 sibling を優先する。
   - `ELSE` branch は `CONDITION` を branch base にする。
9. `_build_ir_node` でノードを構築し、構造ツリーへ接続する。
10. 必要なら `JSON_DESERIALIZE` / `JSON_SERIALIZE` bridge node を自動挿入する。
11. context history を更新し、最終 `logic_tree` を返す。
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

## 5. Operational Notes
- clause 解析や role/path の補助トレースは `src.utils.stdout_guard.debug_print` を通す opt-in 出力とする。
- 通常の IR 生成経路では stdout を使わず、正式な結果は返却される IR 構造に限定する。
