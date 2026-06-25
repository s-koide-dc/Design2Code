# design_parser Design Document

## 1. Purpose (Updated 2026-06-18)

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
5. `validate_structured_spec_or_raise` により構造の整合性を検証し、違反があれば例外を投げる。`kind` / `intent` の高頻度比較は `src.utils.semantic_intents` の共通語彙を使う。
6. `StructuredDesignParser` は `test_cases` を構造化し、`StructuredSpec` の `test_cases` に格納する。
7. `ProjectSpecParser.parse_file/parse_content` は、ヘッダで区切られたセクションを解析して `tech` / `architecture` / `modules` / `entities` / `dtos` / `validation` / `method_specs` / `generation_hints` を辞書化する。
8. **Infer-Then-Freeze (補完→固定化)** を適用する場合、設計書に不足するメタデータを決定的推論で補完し、元文書は保持したまま `.inferred.design.md` を生成してから再パースする。以降の生成は固定化済み `.inferred.design.md` のメタデータのみを使用する。
9. **推論の適用条件**: 明示メタデータが無い場合のみ補完し、既存タグは上書きしない。
10. **推論の安定性**: 固定アセット/固定スコアルールで同一入力に対して同一出力になることを保証する。
11. **推論結果の記録**: 推論を行った場合は `.inferred.design.md` に推論メタデータ（アセットパスと指紋）を記録する。
12. **指紋の算出**: 正規化した設計書本文とアセットのハッシュを結合し、固定ルール版数を含めて SHA-256 を計算する。
13. **補完の現在境界**: 決定的補完で強く扱う literal/source 系は主に `path` / `url` / `sql` と `stdin` / `env` の source 文脈であり、`env` は quoted literal を追加せず `data_source + plain fetch` だけで復元する。
14. **モジュール公開境界**: `design_parser` モジュールは parser/validator だけでなく `infer_then_freeze_if_needed` も公開し、`generate_from_design` や review snapshot CLI から同じ推論入口を利用する。

### Responsibility Boundary
- `StructuredDesignParser` / `validator` は **明示メタデータの解析と検証** を担当する。
- `DesignInferenceEngine` は同一モジュール内の決定的補完入口として機能し、`generate_from_design` や review snapshot CLI から呼ばれる。
- 推論後の固定化先は元の `.design.md` ではなく `.inferred.design.md` である。

### Inference Scope (Reference)
- 補完対象は `KIND/INTENT/TARGET/OUTPUT/SIDE_EFFECT`, `refs`, `data_source`, `semantic_roles` の明示化に限定される。
- 補助 LLM が有効でも accepted 済み `literal_roles_only` suggestion の `path/url/sql` だけを in-memory 反映し、推論器自身は新しい事実を創作しない。

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
- 2026-06-04: `validator` 側の `ACTION/CONDITION/LOOP/ELSE/END` と `FETCH/DATABASE_QUERY` 検証を `src.utils.semantic_intents` の共通定数へ寄せた。
- 2026-06-18: `.inferred.design.md` 固定化、`infer_then_freeze_if_needed` の module-level 公開境界、`env` plain fetch 補完、および literal/source 補完の現行境界を反映。
