# Minimal Design Change Proposal for `spec_role`

## 1. Purpose

この文書は、`IR meaning preservation` 研究で明らかになった `Intent Drift` を抑えるために、IR へ `spec_role` を保持する最小設計変更案をまとめたものである。

目的は、実装を大きく壊さずに、仕様意味 role と runtime role の混線をほどくことである。

## 2. Design Goal

最小設計変更の目標は、以下の 3 点である。

1. 仕様意味としての役割を IR 内で明示的に保持する
2. 既存の `role` フィールドをただちに壊さない
3. 既存の code synthesis や verifier への影響を局所化する

つまり、全面改修ではなく、比較・観測・段階移行に耐える「最小の足場」を作る。

## 3. Proposed Change

### 3.1 New Concept

IR ノードに、既存の `role` とは別に `spec_role` を保持する。

研究上の役割は次のように分担する。

- `intent`
  - 処理意図の既存表現
- `spec_role`
  - 仕様意味 role
- `role`
  - 当面は既存の runtime role として扱う

### 3.2 Storage Location

最小変更案では、`spec_role` は新トップレベル項目にせず、当面 `semantic_map.spec_role` または `semantic_map.semantic_roles.spec_role` に保持する。

理由:

- 現行スキーマとの互換を壊しにくい
- `semantic_map` は既に補助メタの入れ物として使われている
- emitter や既存テストへの影響を限定できる

研究段階では、以下の案を第一候補とする。

`semantic_map.spec_role`

期待 IR では `semantic_map.semantic_roles.spec_role` を使っているが、実装変更時は `semantic_map` 直下へ上げるほうが責務分離としては明確である。

## 4. Recommended Migration Stages

### Stage 0: Research-Only Annotation

現状。

- 期待 IR にだけ `spec_role` を付与する
- 実 IR は既存 `role` を runtime role として読む

### Stage 1: Parser/IR Generator Annotation

次の最小実装変更。

- `StructuredDesignParser` は変更しなくてもよい
- `IRGenerator._analyze_step_integrated` が `spec_role` を返す
- `IRGenerator.generate()` は `node["semantic_map"]["spec_role"]` を保存する
- 既存 `node["role"]` はそのまま残す

### Stage 2: Comparison-Aware Consumers

- `SpecAuditor` や研究用比較ツールが `spec_role` を読めるようにする
- 既存 synthesis は引き続き `role` を参照してよい

### Stage 3: Role Discipline Review

- 必要なら emitter 側が `spec_role` を参照するかを検討する
- この段階で初めて `role` の再定義や縮小を議論する

## 5. Concrete Schema Proposal

最小追加案:

```json
{
  "id": "step_3",
  "type": "ACTION",
  "intent": "LINQ",
  "role": "ACTION",
  "semantic_map": {
    "spec_role": "FILTER",
    "logic": [],
    "semantic_roles": {
      "property": "Price"
    }
  }
}
```

この形なら、既存の `semantic_roles` をそのまま使いながら、role の責務だけを分離できる。

## 6. Why Not Top-Level `spec_role` First

トップレベルに `spec_role` を足す案もあるが、最小変更としては次の不利がある。

- スキーマ更新の影響範囲が大きい
- 既存の JSON 比較やテストが壊れやすい
- 現段階では研究メタとして十分であり、格上げを急ぐ必要がない

したがって、まずは `semantic_map` に保持し、安定したらトップレベル昇格を検討するのが妥当である。

## 7. Expected Benefits

この最小変更で得られる効果は大きい。

### 7.1 Meaning Preservation Visibility

`FILTER`, `DESERIALIZE`, `CHECK` のように runtime 側で潰れる役割も、IR 内に残せる。

### 7.2 Drift Localization

`spec_role` が残っていれば、「仕様意味は保持されたが runtime role に圧縮された」のか、「そもそも解析段階で spec_role を誤った」のかを切り分けやすくなる。

### 7.3 Safer Refactoring Path

既存の `role` 利用コードをすぐ壊さずに、段階的に role 体系を再設計できる。

## 8. Expected Risks

### 8.1 Dual-Role Confusion

`spec_role` と `role` の二重管理で一時的に混乱しやすい。

対策:

- 文書上は `role = runtime_role` と明記する
- 研究用比較では `spec_role` を優先する

### 8.2 Partial Adoption

一部ノードだけ `spec_role` が付いて、一貫性が崩れる可能性がある。

対策:

- 初期導入では最低でも `DESERIALIZE`, `FILTER`, `CHECK`, `TRANSFORM`, `DISPLAY`, `FETCH`, `PERSIST`, `RETURN` を対象にする

### 8.3 False Confidence

`spec_role` を保持しただけで意味保存が達成されたと誤認しやすい。

対策:

- `spec_role` は必要条件であり十分条件ではないと明記する
- dependency, source, cardinality は引き続き別軸で評価する

## 9. Minimal Implementation Boundary

実際に手を入れるなら、初回変更範囲は以下に限定するのが妥当である。

- `src/ir_generator/ir_generator.py`
- 必要なら `schemas/ir_schema.json` の `semantic_map` 説明コメント
- 研究用比較または監査補助の小規模ユーティリティ

逆に、初回から以下には触れないほうがよい。

- `CodeSynthesizer`
- `IREmitter`
- `CodeBuilder`
- `CompilationVerifier`

ここを早く触ると、研究観測と生成修正が混ざる。

## 10. Decision

研究としての最小設計変更案は、次の一文に要約できる。

`IR ノードの既存 role を runtime role と見なし、仕様意味 role は semantic_map 内の spec_role として追加保持する。`

この案は、観測結果、比較作業、既存実装互換性の3点を最もバランスよく満たしている。

## 11. Next Step

この提案の次に進むなら、いよいよ実装段階に入る。

最初の変更は、`IRGenerator._analyze_step_integrated` が `spec_role` を返し、`generate()` がノードへ保存するようにすることになる。
