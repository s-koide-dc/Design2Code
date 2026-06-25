# MethodStorePolicy 設計ドキュメント

## 1. 目的 (Purpose)
`MethodStorePolicy` は、method store に入るメソッド entry を harvest 経路に依存せず同じ規則で正規化し、合成候補として低価値な API を保存前に除外する責任を持つ。

このモジュールは検索クエリの解釈や自然言語からの型推測は行わない。入力済みの構造化 entry に対して、metadata 補完、capability map 適用、policy file に基づく pruning、audit 集計だけを行う。

## 2. 構造化仕様 (Structured Specification)

### 2.1. 入力
- **method_data**: `Dict[str, Any]`
  - `name` と `class` は必須。
  - `id`, `params`, `return_type`, `definition`, `code`, `tags`, `capabilities`, `intent`, `role`, `usings`, `has_side_effects` は任意。
- **workspace_root**: `Optional[str]`
  - `resources/method_store_policy.json` と `resources/method_capability_map.json` の探索起点。
- **capability_map**: `Optional[Dict[str, Any]]`
  - 呼び出し側が既に読み込んだ map を渡せる。未指定なら resources から読み込む。

### 2.2. 出力
- `normalize(method_data)` は、保存可能な entry の場合は正規化済み `Dict[str, Any]` を返す。
- entry が無効または policy により除外される場合は `None` を返す。
- `get_audit_summary()` は `accepted`, `pruned`, `prune_reasons` を含む dict を返す。

### 2.3. 正規化フロー
1. 入力が dict であること、`name` と `class` が空でないことを検証する。
2. `id` と `params` の既定値を補う。
3. `method_capability_map.json` の明示 metadata を適用する。
4. `return_type` と `params[].type` を C# 表記として扱いやすい名前へ正規化する。
5. `params[].role`, `definition`, `has_side_effects`, `usings`, `role`, `origin`, `capabilities`, `summary`, `tags` を補完する。
6. `resources/method_store_policy.json` の pruning ルールを評価する。
7. pruning 対象なら audit に理由を記録して `None` を返す。
8. accepted を加算し、正規化済み entry を返す。

### 2.4. Policy File
`resources/method_store_policy.json` は次の領域を管理する。

- `semantic_roles`: capability に反映できる意味役割。
- `allowed_capabilities`: method store に保存してよい capability。
- `pruning.method_names`: メソッド名単位の除外グループ。
- `pruning.class_suffixes`: class 名末尾による除外グループ。
- `pruning.class_contains`: class 名に含まれる構造的 fragment による除外グループ。
- `pruning.class_prefixes`: namespace/prefix による除外グループ。
- `pruning.exact_classes`: class 完全一致による除外グループ。
- `pruning.method_allowlist_by_class`: class ごとに保存可能な method 名を限定する allowlist。
- `pruning.header_value_suffixes` / `header_value_methods`: HTTP header value parser 群の除外対象。

Policy file が存在しない、壊れている、または一部のキーが欠けている場合は、`_DEFAULT_POLICY` を土台にして読み込み可能な部分だけを反映する。

### 2.5. Capability Map 優先
`resources/method_capability_map.json` に該当メソッドの明示 metadata がある場合は、次を policy 推論より優先する。

- `intent`
- `capabilities`
- `param_roles`

明示 map がある entry は pruning 対象から除外する。これは手動で合成候補として認定した API を policy の広い除外条件から保護するため。

### 2.6. Pruning Audit
`MethodStorePolicy` はインスタンス単位で audit を保持する。

- `accepted`: 正規化され保存可能になった entry 数。
- `pruned`: 除外された entry 数。
- `prune_reasons`: reason ごとの除外数。

`reset_audit()` は harvest 単位で audit を初期化するために使用する。source analysis, reflection, NuGet harvest は、この audit を harvest 結果や `last_policy_audit` として呼び出し側へ渡す。

## 3. 制約
- 自然言語クエリを keyword map や regex で型・機能へ変換しない。
- pruning は構造化済み entry の metadata に対して行う。
- 除外対象を追加する場合は、原則として `resources/method_store_policy.json` を更新する。
- `method_capability_map.json` は明示的な許可・補完として扱い、policy pruning より優先する。
- `sys.` で始まる system seed entry は pruning しない。

## 4. 主な利用者
- `MethodStore`: load/add/save/rebuild 時に entry を正規化し、低価値 API を保存しない。
- `MethodHarvester`: source analysis harvest の entry 作成時に policy を適用し、audit を harvest 結果に含める。
- `DynamicHarvester`: reflection と NuGet harvest の entry 変換時に policy を適用し、`last_policy_audit` に audit を保持する。

## 5. テスト観点
- policy file の pruning rule がコード変更なしで反映される。
- object protocol や lifecycle などの低価値 API が reason 付きで pruned される。
- capability map に明示された entry は pruning から保護される。
- `normalize` は不足 metadata を補完し、保存可能な schema に整える。
- source/reflection/NuGet harvest の各経路で同じ policy が適用される。

## 6. Review Notes
- 2026-06-25: `MethodStorePolicy` 新設。`resources/method_store_policy.json` に基づく正規化・pruning・audit 集計を担当する設計として追加。
