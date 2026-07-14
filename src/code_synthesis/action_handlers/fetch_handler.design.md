# fetch_handler Design Document

## 1. Purpose

`fetch_handler` は stdin / file からの入力取得に対応する FETCH 処理を生成する。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、対象ノード、パス。
- **Type/Format**: `Dict[str, Any]`
- **Example**: `node={"intent":"FETCH","source_kind":"stdin"}` / `node={"intent":"FETCH","source_kind":"file"}`

### Output
- **Description**: 入力取得を含むパス、または `None`。
- **Type/Format**: `List[Dict[str, Any]] | None`

### Core Logic
1. `FETCH` かつ `source_kind=stdin` の場合、`Console.ReadLine()` を生成する。
2. `FETCH` かつ `source_kind=file` の場合、path role を bind し、`error_policy=return_default` では `ReadGeneratedTextFileOrDefault(path, out succeeded)` helper を呼び出す。
3. file read helper が失敗した場合は `StatementBuilder._catch_action_for_policy()` と同じ fallback return を呼び出し元で実行する。
4. `error_policy=continue/rethrow` の file read は従来通り structured resilient wrapper を使う。
5. 生成した変数を `type_to_vars` に登録し、`active_scope_item` を更新する。
6. `FETCH` 判定と statement への intent 付与には `src.utils.semantic_intents` の共通定数を使う。

### Test Cases
- **Happy Path**:
  - **Scenario**: stdin 取得ノード。
  - **Expected Output**: 1行入力のステートメントが生成される。
  - **Scenario**: file 取得ノード。
  - **Expected Output**: text file read helper call と failure guard が生成される。
- **Edge Cases**:
  - **Scenario**: `source_kind` が `stdin` 以外。
  - **Expected Output / Behavior**: `None` を返す。

## 3. Dependencies
- **Internal**: `code_synthesis`

## 4. Review Notes
- 2026-06-04: `FETCH` 判定と statement metadata の intent を `src.utils.semantic_intents` の共通語彙へ寄せた。
- 2026-07-13: file read の `return_default` 経路を `ReadGeneratedTextFileOrDefault` helper と failure guard に寄せる契約へ同期。
