# base_detector Design Document

## 1. Purpose

`BaseSmellDetector` はコードスメル検出器の基底クラスであり、共通の閾値設定とインターフェイスを提供する。

## 2. Structured Specification

### Input
- **Description**: 解析対象ファイル情報としきい値。
- **Type/Format**: `Dict[str, Any]` ほか

### Output
- **Description**: スメル検出結果の配列。
- **Type/Format**: `List[Dict[str, Any]]`

### Core Logic
1. `thresholds` を保持する。
2. `detect` はサブクラス実装を要求する。
3. `detect_roslyn` は既定では空配列を返し、必要に応じて上書きする。

### Test Cases
- **Happy Path**:
  - **Scenario**: サブクラスが `detect` を実装。
  - **Expected Output**: 具体的なスメル検出結果が返る。
- **Edge Cases**:
  - **Scenario**: `detect` が未実装。
  - **Expected Output / Behavior**: `NotImplementedError` が発生する。

## 3. Dependencies
- **External**: `typing`
