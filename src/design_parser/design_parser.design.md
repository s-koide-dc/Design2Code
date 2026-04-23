# design_parser Design Document

## 1. Purpose (Updated 2026-04-14)

`design_parser` は設計書（`.design.md`）やプロジェクト仕様書を、後続の合成パイプラインが消費できる構造化データへ変換する。  
主な入口は以下の 2 つである。

- `StructuredDesignParser`: モジュール設計書を `StructuredSpec` へ変換。
- `ProjectSpecParser`: プロジェクト仕様書をプロジェクト生成用の辞書構造へ変換。

## 2. Structured Specification

### Input
- **Description**: 設計書のパス、もしくは Markdown 文字列。
- **Type/Format**: `str` (File Path / Markdown)
- **Example**: `"src/module_x/module_x.design.md"`

### Output
- **Description**: 解析済みの構造化仕様（`StructuredSpec`）またはプロジェクト仕様辞書。
- **Type/Format**: `Dict[str, Any]`
- **Example**:
  ```json
  {
    "module_name": "SampleModule",
    "purpose": "Sample purpose",
    "inputs": [],
    "outputs": [],
    "steps": [],
    "test_cases": [],
    "data_sources": []
  }
  ```

### Core Logic
1. `StructuredDesignParser.parse_design_file` は `.design.md` を読み込み、`DesignDocParser` による一次パース結果から `StructuredSpec` を構築する。
2. Core Logic の行に含まれる `[data_source|id|kind]` を抽出し、`data_sources` を形成する。
3. 各ステップ行から `[KIND|INTENT|TARGET|OUTPUT|SIDE_EFFECT|SOURCE_REF|SOURCE_KIND]` メタデータ、`[refs:...]`、`[ops:...]`、`[semantic_roles:{...}]` を解析して `steps` に変換する。
4. `source_ref` と `data_sources` を突合し、`source_kind` を補完する。`FETCH` で未指定の場合は `file` を既定値とする。
5. `validate_structured_spec_or_raise` により構造の整合性を検証し、違反があれば例外を投げる。
6. `StructuredDesignParser` は `test_cases` を構造化し、`StructuredSpec` の `test_cases` に格納する。
7. `ProjectSpecParser.parse_file/parse_content` は、ヘッダで区切られたセクションを解析して `tech` / `architecture` / `modules` / `entities` / `dtos` / `validation` / `method_specs` / `generation_hints` を辞書化する。
8. **Infer-Then-Freeze (補完→固定化)** を適用する場合、設計書に不足するメタデータを決定的推論で補完し、`.design.md` へ明示的に書き戻した後に再パースする。以降の生成は書き戻し済みメタデータのみを使用する。
9. **推論の適用条件**: 明示メタデータが無い場合のみ補完し、既存タグは上書きしない。
10. **推論の安定性**: 固定アセット/固定スコアルールで同一入力に対して同一出力になることを保証する。
11. **推論結果の記録**: 推論を行った場合は `.design.md` に推論メタデータ（アセットパスと指紋）を記録する。
12. **指紋の算出**: 正規化した設計書本文とアセットのハッシュを結合し、固定ルール版数を含めて SHA-256 を計算する。

### Responsibility Boundary
- `design_parser` は **明示メタデータの解析のみ** を担当し、推論は行わない。
- 推論（補完→固定化）は `generate_from_design` 側で実行され、書き戻し後の `.design.md` を `design_parser` が再パースする。

### Inference Scope (Reference)
- `design_parser` 自体は推論しないが、補完対象は `KIND/INTENT/TARGET/OUTPUT/SIDE_EFFECT`, `refs`, `data_source`, `semantic_roles` の明示化に限定される。

### Test Cases
- **Happy Path**:
  - **Scenario**: `data_source` と `ops` を含む設計書を解析する。
  - **Input**: `.design.md` ファイルパス。
  - **Expected Output**: `steps` と `data_sources` が整合し、バリデーションが通る。
- **Edge Cases**:
  - **Scenario**: 設計書パスが存在しない。
  - **Input**: 存在しないファイルパス。
  - **Expected Output / Behavior**: `FileNotFoundError` を送出。
  - **Scenario**: 必須キーが欠落した仕様。
  - **Input**: `module_name` を含まない Markdown。
  - **Expected Output / Behavior**: `StructuredSpecValidationError` を送出。

## 3. Dependencies
- **Internal**: `structured_parser`, `project_spec_parser`, `validator`, `design_doc_parser`

## 4. Review Notes
- 2026-04-14: Infer-then-freeze の責務境界と固定化フローの記述を現行実装に合わせて再確認。
