# Dependency Contract Design Document

## 1. Purpose

dependency_contract は生成された .NET プロジェクトへ依存パッケージを出力する前に、名前とバージョンを検証する。
.csproj の XML 文字列連結による設定破壊やインジェクションを防止する。

## 2. Structured Specification

### Input

- **Description**: NuGet 依存関係の辞書列。
- **Type/Format**: Iterable[Dict[str, str]] | None

### Output

- **Description**: 正規化済み依存関係、または安全な XML PackageReference。
- **Type/Format**: List[Dict[str, str]] / str

### Core Logic

1. 各要素が辞書であることを確認する。
2. name と version が空でない文字列であることを確認する。
3. XML 予約文字・改行・制御文字を拒否する。
4. 検証済み値だけを XML エスケープして PackageReference として出力する。

## 3. Error Handling

契約違反は InvalidDependencyError として通知し、未検証の値を .csproj へ出力しない。

## 4. Test Cases

- 通常の package name/version が出力される。
- XML 予約文字、改行、制御文字を拒否する。
- 空値、不正な要素型を拒否する。

