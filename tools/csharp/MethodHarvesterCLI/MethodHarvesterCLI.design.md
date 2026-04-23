# MethodHarvesterCLI Design Document

## 1. Purpose (Updated 2026-04-14)

`MethodHarvesterCLI` は .NET アセンブリから公開メソッドのメタデータを収集し、  
メソッドストア同期用の JSON 形式で出力するコマンドラインツールである。  
属性（Intent/Capabilities/ParamRole）や capability map の定義に基づき、意図・能力・引数ロールを補完する。

## 2. Structured Specification

### Input
- **Description**: 解析対象アセンブリのパスまたは名前の配列。任意で `--map <path>` を指定可能。
- **Type/Format**: `string[]`
- **Example**:
  ```text
  MethodHarvesterCLI --map method_capability_map.json System.Private.CoreLib.dll
  ```

### Output
- **Description**: `methods` 配列を含む JSON を stdout に出力。
- **Type/Format**: JSON (stdout)
- **Example**:
  ```json
  {
    "methods": [
      {
        "id": "system.string.contains",
        "name": "Contains",
        "class": "System.String",
        "returnType": "bool",
        "params": [{"name": "value", "type": "string", "role": null}],
        "isStatic": false,
        "intent": null,
        "capabilities": [],
        "tags": [],
        "code": "{target}.Contains({value})",
        "definition": "Boolean Contains(System.String)",
        "tier": 1
      }
    ]
  }
  ```

### Core Logic
1. `--map <path>` または `METHOD_CAPABILITY_MAP` 環境変数、同梱 `method_capability_map.json` を探索して capability map を読み込む。
2. 引数で与えられたアセンブリを順にロードする（ファイルパス、名前、実行中アセンブリ、System の dll 既定パス）。
3. 公開型のうち Obsolete を除外し、名前空間に `Repo` / `Data.Repo` / `Order` / `Product` を含む型は除外する。
4. 各型の公開メソッドから `MethodInfoData` を生成し、以下を採取する:
   - `Id`, `Name`, `Class`, `ReturnType`, `Params`, `IsStatic`, `Definition`, `Tier`
   - 属性または capability map により `Intent`, `Capabilities`, `ParamRoles` を補完
5. `Code` は static/instance に応じたテンプレート文字列として生成する。
6. 収集結果を JSON に整形して stdout に出力する。

### Test Cases
- **Happy Path**:
  - **Scenario**: System アセンブリを入力。
  - **Expected Output**: `methods` に複数件の公開メソッドが出力される。
- **Edge Cases**:
  - **Scenario**: 不正なアセンブリ指定。
  - **Expected Output / Behavior**: エラーを stderr に出力し、他の入力を継続処理する。

## 3. Dependencies
- **Internal**: なし
- **External**: `.NET Reflection`, `System.Text.Json`, `System.IO`, `System.Linq`

