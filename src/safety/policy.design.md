# SafetyPolicy Design Document

## 1. Purpose

SafetyPolicy は安全ポリシーの既定値と JSON 設定値を型付きの実行モデルへ正規化する。
Planner の事前検証と ActionExecutor の実行時検証が同じポリシーを利用できるようにする。

## 2. Structured Specification

### Input

- **Description**: config/safety_policy.json の内容、または未指定。
- **Type/Format**: Mapping[str, Any] | None

### Output

- **Description**: 破壊的 intent、許可コマンド、サブコマンド、パス制限を保持する独立した SafetyPolicy。
- **Type/Format**: SafetyPolicy

### Core Logic

1. SafetyPolicy() が安全側の既定値を生成する。
2. from_mapping() が設定に存在する項目だけを上書きする。
3. set、list、dict、blocked rule は新しいコンテナへコピーし、インスタンス間の共有状態を防ぐ。
4. 設定にない項目は既定値へフォールバックする。

## 3. Error Handling

不正な型の詳細診断は設定読み込み層の責務とし、本モデルは欠落値に対して安全な既定値を使用する。

## 4. Test Cases

- 既定値が生成される。
- 設定値が既定値を上書きする。
- 生成した二つのモデルのリスト・辞書が相互に変更されない。

