# CALCULATE Role Analysis

## 1. Purpose

この文書は、`CALCULATE` が `GENERAL/ACTION` に弱化する発生条件を局所分析するためのものである。

`structural_dependency_rule` と `structural_role_bridge` により、構造依存と構造 role の整理は進んだ。ここで残る主要課題の 1 つが、`価格を計算する` のような計算ステップが `CALCULATE` として安定しないことである。

## 2. Target Symptom

代表事例:

- `case_10_loop_body_dependency`
  - 期待: `intent=CALC`, `role=CALC`, `spec_role=CALCULATE`
  - 観測: `intent=GENERAL`, `role=ACTION`, `spec_role=ACTION`

つまり現状では、計算操作であっても explicit calculation metadata がないと一般動作へ落ちやすい。

## 3. Code-Level Observation

発生点は [ir_generator.py](/C:/workspace/NLP/src/ir_generator/ir_generator.py:843) 付近にある。

現行ロジックでは `CALC` へ上がる主条件が、

- `logic_goals` 内に `type=calculation` が存在すること

に強く依存している。

一方で `価格を計算する。` のような文は、

- 数式
- 比較値
- 明示的な target_hint

を含まないため、`LogicAuditor` が `calculation` goal を十分に生成できない場合がある。

その結果:

1. `intent_detector` 段階では `GENERAL`
2. `_infer_intent_role_cardinality` でも `CALC` へ上がらない
3. `logic_goals` も空
4. 最終的に `GENERAL/ACTION`

となる。

## 4. Why This Is Different From WRAP / ITERATE

`WRAP` と `ITERATE` は structure node として判別できる。

- `WRAP`: body marker と retry wrapper 判定
- `ITERATE`: `node_type=LOOP`

これに対して `CALCULATE` は、structure ではなく action semantics である。

したがって、

- body の有無
- node_type

だけでは上げられず、ステップ内部の意味理解が必要になる。

## 5. Failure Shape

`CALCULATE` の失われ方は、現時点では主に次の 2 つである。

### 5.1 Goal Absence

計算語があるが、`logic_goals` に calculation goal が立たない。

### 5.2 Target Ambiguity

計算対象の property や quantity が取れず、`target_hint` が弱い。

この場合、たとえ `CALC` に上がっても downstream の精度が安定しない。

## 6. Current Bridge Status

`ActionSynthesizer` 側にはすでに bridge がある。

- `spec_role=CALCULATE` -> `runtime_role=CALC`
- `intent=CALC` -> `handle_calc`

つまり主問題は downstream ではなく、upstream の `IRGenerator` で `CALCULATE` を十分に検出できていないことにある。

## 7. Research Implication

`CALCULATE` は、`CHECK` や `DESERIALIZE` と違って downstream bridge より upstream detection が先である。

したがって次段で考えるべきなのは、

1. `CALCULATE` をどの explicit semantic metadata で立てるか
2. どの程度まで natural language だけで calculation intent とみなすか

である。

## 8. Preferred Direction

このプロジェクトの制約上、安易なキーワードマッチへ戻るべきではない。

したがって、自然なのは次の順である。

1. 研究ケースでは `semantic_roles.target_hint` や `ops` を伴う explicit 計算ケースを追加する
2. `LogicAuditor` が calculation goal を立てる最小条件を明確にする
3. その条件を満たす場合のみ `CALC` へ上げる

つまり、「計算らしい文だから CALC」ではなく、「計算対象と操作意味が取れたから CALC」という基準に寄せる。

## 9. Next Step

この文書の次にやるべきことは、`CALCULATE` 専用の補助ケースを 1 つ追加し、

- explicit target_hint あり
- explicit target_hint なし

の 2 パターンを比較して、検出安定性の差を観察することである。
