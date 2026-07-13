# GenerationQuality Design Document

## 1. Purpose

`generation_quality` は、生成コードがコンパイルできるだけでなく、公開導線に載せられる品質を満たしているかを判定する。
compiler diagnostics、spec audit、blueprint contract、任意の Roslyn source metrics を入力にし、生成コードの品質ゲート結果、maintainability 観測値、maintainability finding を構造化して返す。

## 2. Structured Specification

### Input
- **Description**: 生成コード、`CompilationVerifier` の結果、blueprint、spec audit issues、任意の source metrics。
- **Type/Format**: `str`, `Dict[str, Any]`, `Dict[str, Any]`, `List[str]`, `Dict[str, Any]`

### Output
- **Description**: 品質ゲートの成否、issue 一覧、warning/error/spec issue count、適用チェック一覧、maintainability 観測値と finding。
- **Type/Format**: `Dict[str, Any]`

### Core Logic
1. compiler error があれば品質 NG とする。
2. `fail_on_warnings=True` の場合、compiler warning があれば品質 NG とする。
3. spec audit issue があれば品質 NG とする。
4. 生成コードおよび blueprint に unresolved marker が残っていないか確認する。
   - exact sentinel として `// TODO` と `NotImplementedException` を扱う。
5. blueprint-level semantic assertion として placeholder fetch を確認する。
   - `Enumerable.Empty<T>()` は JSON deserialize fallback として正当な場合があるため、生成コード文字列だけでは禁止しない。
6. maintainability は観測値として出力し、`fail_on_maintainability=True` の実行では CI fail 条件に含める。
   - method 数、class 数、constructor 数、helper method 数、operation method 数、総行数、最大 method 行数、最大 try 数、最大 catch 数、最大 operation method 行数、最大 operation method try 数、最大 operation method catch 数、blueprint statement 数を出す。
   - `source_metrics.status == "success"` の場合は CodeBuilder/Roslyn 由来の AST メトリクスを使い、`analysis_source == "roslyn"` を返す。
   - Roslyn metrics が無い場合だけ Python 側の軽量観測へ fallback し、`analysis_source == "python_fallback"` を返す。
   - class/struct 宣言を型として扱い、constructor を operation method から分離する。一方で `class_count` は生成クラス数の指標として class 宣言だけを数える。
   - `GeneratedErrorLog`、`GeneratedOperationResult`、`GeneratedProcessor` 内の非 public method、`ReadGenerated` / `WriteGenerated` / `SendGenerated` / `RunGenerated` / `Deserialize` prefix の生成 helper は operation method から除外する。
7. maintainability 閾値を超えた項目は `findings` に warning として出す。
   - 既定閾値は operation method 最大 80 行、operation method 最大 try 4、operation method 最大 catch 8、総行数 200、blueprint statement 40。
   - `fail_on_maintainability=True` の場合だけ finding を品質 NG に昇格する。

### Test Cases
- **Happy Path**:
  - **Scenario**: warning/error/spec issue/unresolved marker がない。
  - **Expected Output**: `valid == true`。
- **Edge Cases**:
  - **Scenario**: `CompilationVerifier` が `CS8602` warning を返す。
  - **Expected Output / Behavior**: `valid == false` かつ warning issue が返る。
  - **Scenario**: 生成コードに `NotImplementedException` が残る。
  - **Expected Output / Behavior**: unresolved marker issue が返る。
  - **Scenario**: operation method 行数が閾値を超える。
  - **Expected Output / Behavior**: `maintainability.findings` に warning が入り、既定では `valid == true` のまま。`fail_on_maintainability=True` では `valid == false` に昇格する。
  - **Scenario**: Roslyn source metrics が渡される。
  - **Expected Output / Behavior**: `maintainability.analysis_source == "roslyn"` となり、method/constructor/helper 集計が source metrics から作られる。

## 3. Dependencies
- **Internal**: `semantic_assertions`
- **External**: 任意で CodeBuilder/Roslyn 由来の source metrics

## 4. Review Notes
- 2026-07-09: review snapshot / design generation regression から利用する生成品質ゲートとして追加。コンパイル成功に加え、warning 0、spec issue 0、unresolved marker なしを代表シナリオの合格条件にした。
- 2026-07-10: maintainability 観測値を追加。初期状態では品質 NG にせず、回帰 JSON で傾向を観測する。
- 2026-07-10: maintainability finding と任意 fail 昇格を追加。constructor と operation method を分け、品質悪化を数値で追えるようにした。
- 2026-07-10: operation method try 数を指標化し、resilient block が増えすぎる生成を catch 数とは別に検知できるようにした。
- 2026-07-10: 生成 helper method を operation method から分離し、品質指標が主処理メソッドを表すよう調整。
- 2026-07-13: generation-quality CI では `--fail-on-maintainability` を有効にし、保守性 finding を代表生成回帰の失敗条件に昇格する運用へ更新。
- 2026-07-13: struct constructor と private helper を method 観測で誤って operation method 扱いしないよう、型名正規化と helper 分類を追加。
- 2026-07-13: snapshot/regression では CodeBuilder の Roslyn source metrics を優先し、Python の行/brace 観測は fallback として扱うよう更新。
