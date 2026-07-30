# naming_helpers Design Document

## Purpose

`naming_helpers` は、プロジェクト生成で使う型・名前・CRUDメソッド・DTOマッピングの決定論的な補助規則を提供する。自然文や候補順位から推測せず、Project Specの構造と明示されたプロパティだけを使う。

## Structured Specification

### Input

- DTOとEntityのプロパティ定義、明示DTO mapping、modulesのメソッド宣言、generation hints。

### Output

- CRUD名、nullableを反映した戻り値型、ID型、CreateRequest→EntityとEntity→Responseのプロパティ対応。

### Core Logic

1. 明示mappingがある場合はそのmappingを保持する。
2. 明示mappingがない場合だけ、同名プロパティを対応付ける。
3. Entityに正確に `CreatedAt` という `DateTime` または `DateTimeOffset` プロパティがあり、CreateRequestから対応付けられない場合は、`utcnow` から `CreatedAt` への生成時刻mappingを追加する。
4. Entity→Responseの既定mappingは同名プロパティだけを対象にする。
5. moduleメソッド宣言のnullable記号とIDプロパティ型を、生成するサービス・リポジトリ署名へ反映する。

### Test Cases

- **Happy Path**: CreateRequestとEntityに同名プロパティがある。
  - **Expected**: 同名プロパティだけがCreateRequest→Entityに対応付く。
- **Edge Case**: `CreatedAt: datetime` はEntityだけにある。
  - **Expected**: `utcnow`→`CreatedAt` mappingが追加され、生成DTOは `DateTime.UtcNow` を代入する。
- **Edge Case**: 明示mappingがある。
  - **Expected**: 既定mappingや時刻mappingで上書きしない。

## Dependencies

- External dependencyなし。型名の変換はこのモジュール内の決定論的な規則で完結する。
