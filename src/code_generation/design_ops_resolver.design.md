# DesignOpsResolver Design Document

## 1. Purpose

`DesignOpsResolver` は、設計書の自然言語ステップを既存のmethod-store、定石パターン、canonical knowledgeの候補へ結び付ける。候補探索と採否を分け、採否はintent、型、data source、明示的な構造制約を満たす候補に限定する。

## 2. Structured Specification

### Input
- **Description**: 設計書の自然言語ステップと、必要に応じてローカルのchiVe・JMDict資産。
- **Type/Format**: `str`, `ConfigManager`, optional `VectorEngine`

### Output
- **Description**: 構造制約を満たすstep token、または候補なし。
- **Type/Format**: `tuple[str | None, float]`

### Core Logic
1. Janomeで文を解析し、構文上の主要語と名詞topicを取得する。
2. `dictionary.db` が利用可能なら、topicのJMDict語義を候補検索の文脈として追加する。
3. method-store、structural memory、canonical knowledgeから候補を取得する。
4. chiVe実モデルが利用可能なら、同じ文脈で意味的候補を補助的に取得する。
5. URL、ファイル、intent、型、data source、除外intentなどの構造ヒントで候補を絞り、対応するstep tokenへ写像する。
6. 決定的な構造条件を満たす候補がなければ候補なしを返し、上位層の構造的fallbackまたは明示化要求へ委ねる。

### Test Cases
- **Happy Path**:
  - **Scenario**: JMDictの語義とchiVeがある日本語設計文。
  - **Expected Output**: 語義を含む文脈で候補を拡張し、構造条件を満たす候補だけを返す。
- **Edge Cases**:
  - **Scenario**: 資産なしのCI環境。
  - **Expected Output / Behavior**: 意味候補拡張を行わず、method-storeと構造的fallbackだけで処理する。

## 3. Dependencies
- **Internal**: `morph_analyzer`, `syntactic_analyzer`, `semantic_analyzer`, `method_store`, `unified_knowledge_base`, `structural_memory`
- **Optional local assets**: chiVe cache, JMDict `dictionary.db`

## 4. Notes
- chiVeとJMDictは候補の再現範囲を広げる補助資産であり、タグ、型、source、条件論理を推測だけで確定するためには使わない。
- 資産が無い場合は警告や失敗にせず、同じ構造検証境界の軽量経路を維持する。
