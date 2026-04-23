# config Design Document

## 1. Purpose

`config` は設定ファイル群を読み込み、パス解決と設定取得 API を提供する。

## 2. Structured Specification

### Input
- **Description**: ワークスペースルート（省略時は CWD）。
- **Type/Format**: `str | None`
- **Example**: `"C:\\workspace\\NLP"`

### Output
- **Description**: 設定辞書と各種パスを保持する `ConfigManager` インスタンス。
- **Type/Format**: `ConfigManager`

### Core Logic
1. `config/` 配下の JSON（`config.json`, `safety_policy.json`, `retry_rules.json` など）を読み込む。
2. 読み込み失敗時は空辞書として扱う。
3. `resources/` 配下の各種パス（辞書・モデル・定義ファイル）を解決して保持する。
4. `get` / `get_section` で設定値を取得する。

### Test Cases
- **Happy Path**:
  - **Scenario**: 設定ファイルが存在する。
  - **Expected Output**: 辞書が読み込まれ、`get` で取得できる。
- **Edge Cases**:
  - **Scenario**: 設定ファイルが存在しない。
  - **Expected Output / Behavior**: 空辞書が返る。

## 3. Dependencies
- **Internal**: `config_manager`
- **External**: `json`, `os`, `pathlib`, `typing`
