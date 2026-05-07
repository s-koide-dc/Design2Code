# DesignInferenceEngine Design Document

## 1. Purpose

`DesignInferenceEngine` は明示 metadata が不足する `.design.md` に対して、固定資産と固定ルールに基づく決定的補完を一度だけ行い、その結果を `.inferred.design.md` として固定化する。

## 2. Structured Specification

### Input
- **Description**: 元の `.design.md` パス。
- **Type/Format**: `str`
- **Example**: `"scenarios/sample.design.md"`

### Output
- **Description**: 推論結果ステータス、必要なら出力先 `.inferred.design.md`。
- **Type/Format**: `Dict[str, Any]`
- **Example**: `{"status":"updated","output_path":"...sample.inferred.design.md"}`

### Core Logic
1. 設計書本文を読み込み、`DesignDocParser` で Core Logic と出力仕様を取得する。
2. data source 行を先に収集し、後続ステップの source 解決候補として保持する。
3. 各 Core Logic 行について、明示タグがある行はそのまま保持し、無い行のみ補完対象にする。
4. `DesignOpsResolver` と entity 推定を使って、`intent`, `target_entity`, `output_type`, `refs`, `semantic_roles`, `data_source` を決定的に推論する。
5. confidence threshold を下回る場合は補完せず `blocked` を返す。
6. 変更があれば元文書は書き換えず、`.inferred.design.md` に書き出す。
7. `### Inference Metadata` ブロックを埋め込み、推論ルール版と asset fingerprint を追跡可能にする。

### Test Cases
- **Happy Path**:
  - **Scenario**: 明示 metadata が不足する通常ステップ。
  - **Expected Output**: `.inferred.design.md` が生成され、`status=updated`。
- **Edge Cases**:
  - **Scenario**: confidence が閾値未満。
  - **Expected Output / Behavior**: `status=blocked` と issue 一覧を返す。
  - **Scenario**: 変更不要。
  - **Expected Output / Behavior**: `status=no_change` を返す。

## 3. Dependencies
- **Internal**:
  - `config_manager`
  - `design_doc_parser`
  - `design_ops_resolver`
  - `morph_analyzer`
  - `data_source_utils`
  - `entity_inference`
- **External**: なし

## 4. Notes
- 元の `.design.md` を直接更新しない。規約どおり `.inferred.design.md` を生成する。
