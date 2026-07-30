# compact_step_expander 設計ドキュメント

## 1. Purpose

`compact_step_expander` は、設計書の Core Logic 内に書かれた限定的なコンパクトステップ記法を、完全な明示ステップタグへ決定的に展開する。自由文、キーワード照合、類似度、候補スコアによる意図推測は行わない。

## 2. Structured Specification

### Input

- **Description**: `.design.md` の全文。
- **Type/Format**: `string`
- **Compact Syntax**: `[step|INTENT|TARGET|OUTPUT|source=<id>|source_kind=<kind>]`

### Output

- **Description**: 展開済み設計書本文と構文エラー一覧。
- **Type/Format**: `(string, list[CompactStepError])`

### Core Logic

1. `### Core Logic` 節だけを対象にする。ほかの節のテキストは変更しない。
2. `[step|...]` の各フィールドを区切り文字で厳密に解析する。
3. 対応する定型 ACTION のみ受理する。
   - `FETCH`, `FILE_IO`, `PERSIST`, `HTTP_REQUEST`, `JSON_DESERIALIZE`, `LINQ`, `TRANSFORM`, `CALC`, `DISPLAY`, `RETURN`
4. intent 固有の固定表から `ACTION` node kind と side effect を決定する。
5. `FETCH`, `FILE_IO`, `PERSIST`, `HTTP_REQUEST` では `source` と `source_kind` の両方を必須にする。
6. 正しい入力を完全タグへ展開する。例:
   - `[step|FETCH|string|string|source=APP_MODE|source_kind=env]`
   - `[ACTION|FETCH|string|string|IO|APP_MODE|env]`
7. 未対応intent、必須source不足、重複option、未閉鎖タグなどは `CompactStepError` として返す。推測による補完はしない。

### Test Cases

- **Happy Path**: env source の `FETCH` と `DISPLAY` を展開する。
- **Edge Case**: source の無い `FETCH` はエラーにする。
- **Boundary**: Core Logic 外の `[step|...]` は変更しない。

## 3. Dependencies

- **Internal**: `inference_line_syntax`
- **External**: なし

## 4. Notes

- 条件分岐・ループ・複数の意味に読める操作はコンパクト記法の対象外とし、完全タグを必要とする。
- コンパクト記法は完全IRの別表現ではなく、完全タグへ変換するための限定入力形式である。
