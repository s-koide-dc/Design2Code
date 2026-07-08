# DummyDataFactory Design Document

## 1. Purpose
`DummyDataFactory` は、TDDの自己修復サイクルにおいて、不足しているテストデータ（Mockの戻り値や引数）を自動生成するための、型ベースのインスタンス化エンジンです。

## 2. Structured Specification

### 2.1 Input
- **Constructor**:
    - `analysis_results` (Optional[Dict]): Roslyn解析結果（ナレッジグラフ）。
    - `knowledge_base` (Any): 永続化された型知識。
- **Method `generate_instantiation`**:
    - `type_name` (string): C#の型名（例: `int`, `List<string>`, `Task<OrderItem>`, `DataItem`）。

### 2.2 Output
- `instantiation_code` (string): その型をインスタンス化するためのC#コードスニペット（例: `new List<string>()`, `new DataItem { Value = "test" }`）。

### 2.3 Core Logic
1. **プリミティブ型判定**:
    - `int`/`long` -> `0`
    - `string` -> `""`
    - `bool` -> `true`
    - `decimal`/`double` -> `1.0m`/`1.0`
2. **コレクション・ジェネリクス対応**:
    - `T[]` (配列) -> `new T[0]`
    - `List<T>` / `IEnumerable<T>` -> `new List<T>()`
3. **モック化判定 (Auto-Mocking)**:
    - インターフェース（`I`で始まる）または `Service`, `Provider`, `Client` 等のサフィックスを持つ型の場合、`Substitute.For<T>()` を生成。
4. **型駆動のプロパティ値生成**:
    - `register_property(type_name, property_name, property_type)` でRoslyn等が解決した構造化型情報だけを受け付ける。
    - string、数値、bool、DateTime、配列、コレクション、具象参照型を型に基づく決定論的な式へ変換する。
    - プロパティ名のキーワードから値を推測しない。
5. **非構造化失敗の扱い**:
    - `learn_from_failure` はエラーメッセージから型・プロパティを推測せず `False` を返す。
    - 必要な型情報が無い場合はルールを追加せず、後段の実テスト検証により不完全な修正を拒否する。
6. **ナレッジグラフ連携**:
    - Roslyn解析データがある場合、コンストラクタのシグネチャを確認し、再帰的に引数を生成してインスタンス化を試みる。
    - `register_accessed_properties` はSUTメソッドの `accesses` symbol IDと戻り値型のプロパティIDを照合し、一致したプロパティだけを初期化対象へ登録する。
7. **デフォルトフォールバック**:
    - 未知のクラスの場合、デフォルトコンストラクタ `new ClassName()` を生成。

## 3. Test Cases

### 3.1 Happy Path
- **Input**: `List<string>`
- **Output**: `new List<string>()`

### 3.2 Structured Property Path
- **Scenario**: Roslyn解析が `User.Profile: Example.Profile` を解決。
- **Action**: `register_property("User", "Profile", "Example.Profile")` を呼び出す。
- **Input**: `User`
- **Output**: `new User { Profile = new Profile() }`
