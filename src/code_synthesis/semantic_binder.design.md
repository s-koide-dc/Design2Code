# SemanticBinder Design Document

## 1. Purpose

`SemanticBinder` は IR metadata を具体的な C# パラメータと条件式へ変換する。  
現在は特に `CHECK` metadata と provenance-strength を消費して、過剰具体化しない条件式合成を行う。

## 2. Structured Specification

### Input
- **Description**: メソッド定義、IR ノード、現在の synthesis path。
- **Type/Format**: `Dict[str, Any]`, `Dict[str, Any]`, `Dict[str, Any]`

### Output
- **Description**: バインド済みパラメータ列、条件式、解決済み source variable。
- **Type/Format**: `List[str]`, `str`, `Tuple[str, Optional[str]]`

### Core Logic
1. `bind_parameters` は semantic roles、literal map、context 変数、default fallback を順に使って引数を決める。
2. `path`, `url`, `sql` は literal continuity を保つが、誤 bleed は抑止する。
3. `_resolve_source_var` は型・role・recency に基づいて source 変数を解決する。
4. `generate_logic_expression` は `logic` を走査して条件式を組み立てる。predicate の property を schema と明示 semantic role から一意に解決できない場合は、任意の先頭 property を選ばず `None` を返して上流の synthesis path を棄却する。
   - calculation の対象も同じ契約に従い、`Total` や先頭 property への補完は行わない。
   - numeric predicate は明示的な数値リテラルまたは束縛済み数値変数だけを受け付け、未束縛の `{input}` や不正な値を `0` に置換しない。logic が一つも生成できない場合も `true` を返さず `None` とする。
   - numeric predicate の対象が string property の場合、`StartsWith` や equality へ意味を変換せず `None` を返す。
   - string predicate の対象が string property 以外の場合も、instance method 呼び出しを生成せず `None` を返す。
   - predicate の `negated=true` は個々の生成式全体を否定し、nullable string guard を含む場合も括弧で意味を保持する。
5. `spec_role=CHECK` の場合は `_build_check_expression` を優先し、`check_kind`, `check_subject`, `check_operator`, `check_value`, `source_kind`, `subject_resolution` から直接式を組み立てる。ただし IR が `structured_logic=true` を明示した場合は、その `logic` 配列を正とし、CHECK/EXISTS の便宜的な fallback を適用しない。
6. weak provenance の場合は schema/property reverse lookup を抑止する。
7. `history_subject` のような middle-strength provenance は exact target scope に閉じた解決だけを許可する。
8. `HTTP_REQUEST` で `semantic_roles.payload` または `semantic_roles.content` が明示され、値が `{context}` の場合は、current context item を優先解決して `new StringContent(JsonSerializer.Serialize(contextVar))` を組み立てる。
9. 上記 HTTP content 解決では、明示 payload/content がある限り write-role に限定せず、loop item や active scope item を request body として利用できる。
10. nullable-enabled verification を前提に、schema 由来の string property へ `Contains` / `StartsWith` などの instance method を出す場合は null guard を付与する。

### Test Cases
- **Happy Path**:
  - **Scenario**: `exists_check` で file path が明示されている。
  - **Expected Output**: `File.Exists(...)` を生成する。
- **Edge Cases**:
  - **Scenario**: weak `subject_resolution` で property reverse lookup が必要になる。
  - **Expected Output / Behavior**: 過剰具体化せず generic path に留まる。
  - **Scenario**: `intent=EXISTS` に分類された条件ノードに、`Total > 5000 AND CustomerType == Premium` の構造化 `logic` がある。
  - **Expected Output / Behavior**: `File.Exists(...)` へ退避せず、すべての predicate を C# 条件式として生成する。

## 3. Dependencies
- **Internal**:
  - `text_parser`
  - `type_system`
- **External**: なし

## 4. Review Notes
- 2026-06-04: `DATABASE_QUERY` / `FETCH` / `PERSIST` / `HTTP_REQUEST` / `EXISTS` と READ/WRITE/PERSIST/FETCH/TRANSFORM の高頻度比較を `src.utils.semantic_intents` の共通語彙へ寄せた。
- 2026-06-24: `HTTP_REQUEST + payload:{context}` のとき current context item を `StringContent(JsonSerializer.Serialize(...))` へ変換する現在の binding 境界を反映。
- 2026-07-09: schema string property に対する string method 条件式で null guard を出し、生成コードの nullable warning を品質ゲートで検出可能な状態へ同期。
- 2026-07-22: 明示された `structured_logic` は intent 分類より優先する。これにより CONDITION が `EXISTS` と正規化されていても、構造化された複合 predicate をファイル存在チェックへ置換しない。
- 2026-07-23: 明示 predicate の `negated=true` を条件式単位で保持する契約を反映。
