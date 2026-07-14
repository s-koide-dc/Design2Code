# json_handler Design Document

## 1. Purpose

`json_handler` は JSON デシリアライズを行い、結果変数をパスに登録する。

## 2. Structured Specification

### Input
- **Description**: ActionSynthesizer、JSON ノード、パス。
- **Type/Format**: `Dict[str, Any]`

### Output
- **Description**: デシリアライズ処理を含むパス配列。
- **Type/Format**: `List[Dict[str, Any]]`

### Core Logic
1. `semantic_roles` から `json_var/source_var` を取得し、無ければ `active_scope_item` を利用する。
2. 出力型が未指定なら `target_entity` から推定し、コレクションの場合は `List<T>` にする。
3. 既定の空コレクション式を用意する。
4. `error_policy=return_default` かつ空コレクション fallback がある場合は、operation method 内に `JsonSerializer.Deserialize<T>` の `try/catch` を直接展開せず、`StatementBuilder.ensure_json_deserialize_helper()` が登録する helper を呼び出す。
5. helper 呼び出しは `out bool succeeded` を受け取り、JSON パース失敗時は既存の catch return policy と同じ fallback action を呼び出し元で実行する。これにより operation method の try/catch 密度を下げつつ、パース失敗時の戻り値契約を維持する。
6. `error_policy=continue/rethrow` または空コレクション fallback が無い場合は、従来通り `StatementBuilder.wrap_with_try_catch()` の resilient statement にする。
7. 生成した変数を `type_to_vars` と `active_scope_item` に登録する。
8. 必要な `using` を追加し、エンティティ登録を行う。
9. file-read bridge で補助的に発行する statement intent には `src.utils.semantic_intents` の `FILE_IO` を使う。

### Test Cases
- **Happy Path**:
  - **Scenario**: `target_entity` を指定した JSON デシリアライズ。
  - **Expected Output**: helper 内に `JsonSerializer.Deserialize<T>` が生成され、呼び出し元は helper call と failure guard を持つ。
- **Edge Cases**:
  - **Scenario**: 入力変数が見つからない。
  - **Expected Output / Behavior**: `"{}"` をデフォルト入力として利用する。

## 3. Dependencies
- **Internal**: `code_synthesis`

## 4. Review Notes
- 2026-06-04: JSON source file bridge の statement intent を `src.utils.semantic_intents.INTENT_FILE_IO` へ統一した。
- 2026-07-13: `return_default` の collection JSON deserialize は helper 化し、`out bool succeeded` によってパース失敗時の既存 fallback return 契約を維持する方針へ同期。
