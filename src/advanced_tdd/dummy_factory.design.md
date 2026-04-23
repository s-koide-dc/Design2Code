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
4. **セマンティックな値推測**:
    - プロパティ名に基づき、テストに適した値を割り当てる。
    - `Email` -> `"test@example.com"`, `Name` -> `"Test User"`, `Age` -> `25`, `Amount/Price` -> `10/1000` 等。
5. **Dynamic Learning (Type Learning Loop)**:
    - **Failure Analysis**: `TestFailure` を受け取り、`NullReferenceException` のスタックトレースやメッセージから、不足しているプロパティ名（例: "User.Profile" の "Profile" が null）を抽出。
    - **Rule Update**: 学習したプロパティ名をその型に対応付け、以降の `generate_instantiation` で `new User { Profile = ... }` のようにオブジェクト初期化子に含める。
6. **ナレッジグラフ連携**:
    - Roslyn解析データがある場合、コンストラクタのシグネチャを確認し、再帰的に引数を生成してインスタンス化を試みる。
7. **デフォルトフォールバック**:
    - 未知のクラスの場合、デフォルトコンストラクタ `new ClassName()` を生成。

## 3. Test Cases

### 3.1 Happy Path
- **Input**: `List<string>`
- **Output**: `new List<string>()`

### 3.2 Learning Path
- **Scenario**: `User` クラスで `Profile` プロパティが null で落ちたログを学習。
- **Action**: `learn_from_failure` を呼び出し。
- **Input**: `User`
- **Output**: `new User { Profile = new Profile() }` (Profileプロパティが自動的に含まれる)
