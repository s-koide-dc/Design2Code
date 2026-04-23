# DesignDocParser Design Document

## 1. Purpose (Updated 2026-02-10)
`DesignDocParser`は、プロジェクト標準の `.design.md` 形式で記述された設計書を読み取り、プログラムが解析・検証可能な構造化データ（JSON形式）に変換することを目的とします。これにより、仕様（設計書）と実装（ソースコード）の自動的な整合性チェックが可能になります。

## 2. Structured Specification

### Input
- **Description**: `.design.md` ファイルのパスまたはファイル内容（文字列）。
- **Type/Format**: `string` (path) または `string` (content)。

### Output
- **Description**: 構造化された設計データ。
- **Type/Format**: `Dict`
- **Example**:
  ```json
  {
    "module_name": "SampleModule",
    "purpose": "説明文...",
    "specification": {
      "input": { "description": "...", "format": "...", "example": "..." },
      "output": { "description": "...", "format": "...", "example": "..." },
      "core_logic": [
        "ステップ1...",
        "ステップ2..."
      ]
    },
    "test_cases": [
      { "type": "happy_path", "scenario": "...", "input": "...", "expected": "..." },
      { "type": "edge_case", "scenario": "...", "input": "...", "expected": "..." }
    ]
  }
  ```

### Core Logic
1.  **セクション分割**: 見出し（## 1. Purpose, ## 2. Structured Specification等）に基づいてコンテンツを辞書に分割。数字の有無に関わらず柔軟にマッチング。
2.  **モジュール名抽出**: H1ヘッダーからモジュール名を特定。`# [Name] Design Document` 形式などを考慮。
3.  **各セクションのパース**:
    - `Purpose`: プレーンテキストとして抽出。
    - `Input/Output`: 箇条書き（`- **Description**:` 等）や複数行のコードブロック（```json...```）から情報を抽出。
    - `Core Logic`: 番号付きリストや箇条書きをステップごとのリストとして保持。
    - `Test Cases`: `- Scenario`, `- Input`, `- Expected` といったキーワードに基づき構造化。コードブロック内の入力/期待値も正確に収集。
4.  抽出されたデータを辞書形式にまとめて返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 標準的な設計書（AIFiles/templates/design_document.mdベース）を正しくパースできること。
- **Edge Cases**:
  - **Scenario**: セクションが欠落している設計書。
  - **Expected Output**: 欠落部分は null または空リストとして返し、エラーで停止しないこと。
  - **Scenario**: Core Logic がリスト形式ではない。
  - **Expected Output**: 全文を単一のステップとして保持すること。

## 3. Dependencies
- **Internal**: なし
- **External**: `re` (Python 標準正規表現ライブラリ)
