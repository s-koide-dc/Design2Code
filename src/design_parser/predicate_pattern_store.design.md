# PredicatePatternStore Design Document

## 1. Purpose

`PredicatePatternStore` は、runtime oracleで検証済みの設計シナリオから得た条件predicateの例を、ローカルchiVe環境で候補として取得する。候補は来歴を持つが、それ自体で生成条件を確定しない。

## 2. Structured Specification

### Input
- **Description**: 自然言語の条件文、任意のchiVe `VectorEngine`、検証済みpredicateカタログ。
- **Type/Format**: `str`, optional `VectorEngine`, JSON

### Output
- **Description**: 類似predicate候補と、そのscenario来歴。
- **Type/Format**: `List[Dict[str, Any]]`

### Core Logic
1. `resources/predicate_patterns.json` からgoal、値の種類、対象型、provenanceを持つ有効なパターンだけを読む。
2. chiVe実モデルがある場合だけ、自然文とpattern utteranceをベクトル化する。
3. 候補を来歴付きで返す。
4. 呼出側はschema property、値型、data source、明示構造と照合して初めてpredicateを確定できる。
5. `PropertySemanticStore` はentity schemaに作者が記録したproperty semanticsを同じローカルchiVeで検索し、対象entityと必要な型に限定してproperty候補を返す。

### Test Cases
- **Happy Path**:
  - **Scenario**: 有効な検証済みpatternとchiVe実モデルがある。
  - **Expected Output**: provenanceを保った候補が返る。
- **Edge Cases**:
  - **Scenario**: 実モデルがない。
  - **Expected Output / Behavior**: 候補を返さず、構造的経路を維持する。

## 3. Dependencies
- **Internal**: `config_manager`, optional `morph_analyzer`
- **Optional local assets**: chiVe cache

## 4. Notes
- pattern catalogは自然言語の正規表現・キーワード規則ではない。検証済みsemantic goalを持つ検索用資産である。
- similarityは候補の並び替えだけに使い、しきい値を満たしただけで条件を採用してはならない。
