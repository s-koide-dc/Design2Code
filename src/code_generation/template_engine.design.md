# template_engine Design Document

## 1. Purpose

`template_engine` はテンプレートファイルの読み込み・キャッシュ・文字列置換を行う。

## 2. Structured Specification

### Input
- **Description**: テンプレート名と差し込み値、または JSON テンプレート名。
- **Type/Format**: `str`, `Dict[str, Any]`
- **Example**: `("program.cs.tmpl", {"Namespace": "OrdersProject"})`

### Output
- **Description**: レンダリング済み文字列、または JSON オブジェクト。
- **Type/Format**: `str` / `Dict[str, Any]`
- **Example**: `"namespace OrdersProject;"`

### Core Logic
1. `base_dir` とテンプレート名からパスを構築する。
2. 既にキャッシュ済みならキャッシュを返す。
3. テンプレートを読み込み、`format_map` により値を差し込む。
4. JSON テンプレートは `load_json` で読み込み、辞書として返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: テンプレート文字列をレンダリングする。
  - **Expected Output**: 指定された値が差し込まれた文字列になる。
- **Edge Cases**:
  - **Scenario**: 同じテンプレートを複数回読み込む。
  - **Expected Output / Behavior**: キャッシュが利用される。

## 3. Dependencies
- **Internal**: なし
