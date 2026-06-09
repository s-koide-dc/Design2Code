# fallbacks Design Document

## 1. Purpose

`fallbacks` は IO/DB 等の処理で候補が得られない場合の最小フォールバックを提供する。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、対象ノード、パス。
- **Type/Format**: `Dict[str, Any]`
- **Example**: `node={"intent":"FETCH","source_kind":"stdin"}`

### Output
- **Description**: フォールバック処理済みパス、または `None`。
- **Type/Format**: `List[Dict[str, Any]] | None`

### Core Logic
1. `FETCH + stdin` の場合は `Console.ReadLine()` を生成する。
2. `int` 取得の簡易ケースでは `Counter.GetCount()` を呼び出す。
3. `semantic_roles.sql` がある場合は `Db.Query<T>` の呼び出しに変換する。
4. 該当しない場合は `None` を返す。
5. `FETCH` / `DATABASE_QUERY` の判定と statement intent には `src.utils.semantic_intents` の共通定数を使う。

### Test Cases
- **Happy Path**:
  - **Scenario**: `FETCH` + `stdin`。
  - **Expected Output**: `Console.ReadLine()` が生成される。
- **Edge Cases**:
  - **Scenario**: SQL 情報が無い。
  - **Expected Output / Behavior**: `None` が返る。

## 3. Dependencies
- **Internal**: `code_synthesis`

## 4. Review Notes
- 2026-06-04: `FETCH` / `DATABASE_QUERY` の fallback 判定と statement metadata を `src.utils.semantic_intents` の共通語彙へ寄せた。
