# utils Design Document

## 1. Purpose (Updated 2026-04-14)

`utils` は設計書解析や監査、テキスト解析、リトライ、ビルダー連携など、プロジェクト横断の補助機能を提供する。

## 2. Structured Specification

### Input
- **Description**: コンテキスト辞書や文字列パス。
- **Type/Format**: `Dict[str, Any]` / `str`

### Output
- **Description**: 要約辞書、正規化済みパス、抽出パス。
- **Type/Format**: `Dict[str, Any]` / `str`

### Core Logic
1. `design_doc_parser` は Markdown から Purpose / Spec / Test Cases を抽出する。
2. `design_doc_refiner` は設計書と実装の差分・不整合を監査する。
3. `logic_auditor` は数値条件などの論理ゴールと実装コードの整合を検査する。
4. `text_parser` は URL/SQL パラメータやパス候補の抽出を行う。
5. `retry_utils` はリトライ制御を提供する。

### Test Cases
- **Happy Path**:
  - **Scenario**: `normalize_path` で `C:\\work\\a.txt` を正規化。
  - **Expected Output**: `C:/work/a.txt`。
- **Edge Cases**:
  - **Scenario**: `context` が `None`。
  - **Expected Output / Behavior**: 既定のエラー要約を返す。

## 3. Dependencies
- **Internal**: `design_doc_parser`, `design_doc_refiner`, `logic_auditor`, `text_parser`, `retry_utils`
- **External**: `os`, `re`, `json`

## 4. Review Notes
- 2026-04-14: normalize_path を含む補助機能の役割と依存関係を現行実装に合わせて再確認。
