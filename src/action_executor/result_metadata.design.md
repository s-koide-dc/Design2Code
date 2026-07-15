# ActionResultMetadata Design Document

## 1. Purpose

ActionResultMetadata は ActionExecutor の実行結果を対話層が利用する共通形式へ補完する。
アクション実行や業務処理そのものは担当しない。

## 2. Structured Specification

### Input

- **Description**: pipeline context、action method name、action parameters。
- **Type/Format**: dict, str, Mapping[str, Any]

### Output

- **Description**: action_result.dialogue_metadata と必要な target_name を補完した context。
- **Type/Format**: None

### Core Logic

1. action_result が辞書でなければ何もしない。
2. dialogue_metadata を生成し、action method と intent を設定する。
3. filename、project path、goal description などの主要パラメータを補完する。
4. 対話応答向けの target_name を設定する。
5. 既に存在する値は上書きしない。

## 3. Test Cases

- metadata が存在しない結果に metadata が追加される。
- 既存 metadata が保持される。
- entity wrapper 形式の値が resolver 経由で解決される。
- 不正な action result を安全に無視する。

