# Dependency Loss Trace

## 1. Purpose

この文書は、`dependency_loss_analysis.md` で特定した代表事例について、`IRGenerator` の実装レベルで発生点を固定するためのものである。

初回対象は、`RobustConfigLoader` における `else_children.input_link` の誤接続である。

## 2. Target Symptom

対象ケース:

- `case_04_robust_config_loader`

期待:

- `step_5` は `else_children` に属し、`input_link = step_1` で条件ノードに依存する

観測:

- `step_5` は `else_children` に属するが、`input_link = step_3`

これは `Edge Misbinding` の代表例である。

## 3. Relevant Code Path

主要経路は [ir_generator.py](src/ir_generator/ir_generator.py:243) 以降にある。

問題に直接関与しているのは次の 3 段階である。

1. 通常ノードの `input_link` 決定
2. `ELSE` での `block_stack` 切り替え
3. `last_node_id` / `context_history` の維持

## 4. Trace

### 4.1 then 側ノードまで

`step_3` 生成後、通常経路で次が更新される。

- `last_node_id = step_3`
- `context_history[-1].node_id = step_3`

この時点では妥当である。

### 4.2 ELSE 到達時

`ELSE` 句に入ると、[ir_generator.py](src/ir_generator/ir_generator.py:405) 付近で次が起きる。

- `block_stack` を逆順に走査
- 直近の `CONDITION` を見つける
- その entry の `target` を `"else_children"` に切り替える

つまり、ぶら下げ先だけは正しく切り替わる。

一方で、この分岐では次が起きない。

- `last_node_id` のリセット
- `last_node_id` の条件ノードへの巻き戻し
- else 分岐専用の chaining 文脈への切り替え

## 5. Why Misbinding Happens

次の else 側実ノードを作るとき、通常の chaining 規則 [ir_generator.py](src/ir_generator/ir_generator.py:243) がそのまま適用される。

現在の条件は次の通りである。

- `is_chaining = True`
- `last_node_id = step_3`
- `is_notification = False`

その結果:

- `input_link = last_node_id`
- すなわち `input_link = step_3`

その後、ノード追加時には `block_stack[-1].target == "else_children"` なので、配置先だけは `else_children` になる。

つまり現象は、

1. ノードの配置先は else 側へ切り替わる
2. しかし依存先は then 側の直前ノードを引き継ぐ

という二層不整合である。

## 6. Root Cause

根本原因は、`ELSE` を「構造の向き変更」としてしか扱っておらず、「chaining 文脈の分岐切り替え」として扱っていないことである。

より具体的には、`ELSE` 処理に以下が欠けている。

- else 分岐の基準ノードを条件ノードへ戻す規則
- then 側 `last_node_id` を else 側へ持ち越さない規則
- `input_link` 決定時に構造親を優先する規則

## 7. Minimal Fix Direction

この段階では実装変更はまだ入れないが、修正方針としては次の 2 案に絞られる。

### Option A

`ELSE` に入った時点で、対応する `CONDITION` ノード id を else branch base として保持し、以後の else 側ノードの既定 `input_link` に使う。

### Option B

`input_link` の自動 chaining 時に、現在の親が `CONDITION` の `else_children` である場合は `last_node_id` より親条件ノード id を優先する。

現状の最小変更としては `Option A` のほうが局所的で、依存規則の意図も明確である。

## 8. Broader Implication

この事例は、`Dependency Loss` が単なる属性欠落ではなく、「構造親」と「直前ノード」のどちらを依存基準にするかという規則設計の問題であることを示している。

したがって、今後 `LOOP` や `WRAPPER` を直す際も、

- 直前ノードチェーン
- 構造親への従属

を同一ルールで済ませないほうがよい。

## 9. Next Step

次に進めるなら、`ELSE` の branch base を明示的に持つ最小修正を `IRGenerator` に入れ、`case_04_robust_config_loader` の `input_link` が `step_1` に戻るかを確認するのが自然である。
