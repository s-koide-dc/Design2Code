# fetch_handler Design Document

## 1. Purpose

`fetch_handler` は stdin からの入力取得に対応する FETCH 処理を生成する。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、対象ノード、パス。
- **Type/Format**: `Dict[str, Any]`
- **Example**: `node={"intent":"FETCH","source_kind":"stdin"}`

### Output
- **Description**: 入力取得を含むパス、または `None`。
- **Type/Format**: `List[Dict[str, Any]] | None`

### Core Logic
1. `FETCH` かつ `source_kind=stdin` の場合、`Console.ReadLine()` を生成する。
2. 生成した変数を `type_to_vars` に登録し、`active_scope_item` を更新する。

### Test Cases
- **Happy Path**:
  - **Scenario**: stdin 取得ノード。
  - **Expected Output**: 1行入力のステートメントが生成される。
- **Edge Cases**:
  - **Scenario**: `source_kind` が `stdin` 以外。
  - **Expected Output / Behavior**: `None` を返す。

## 3. Dependencies
- **Internal**: `code_synthesis`
