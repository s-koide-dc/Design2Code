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
3. 既定の空コレクション式を用意し、`JsonSerializer.Deserialize<T>` に `??` で連結する。
4. 生成した変数を `type_to_vars` と `active_scope_item` に登録する。
5. 必要な `using` を追加し、エンティティ登録を行う。

### Test Cases
- **Happy Path**:
  - **Scenario**: `target_entity` を指定した JSON デシリアライズ。
  - **Expected Output**: `JsonSerializer.Deserialize<T>` が生成される。
- **Edge Cases**:
  - **Scenario**: 入力変数が見つからない。
  - **Expected Output / Behavior**: `"{}"` をデフォルト入力として利用する。

## 3. Dependencies
- **Internal**: `code_synthesis`
