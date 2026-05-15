# Wrap Timeout Semantics Design

## 1. Purpose

この文書は、`spec_role=WRAP` かつ explicit `wrapper_kind=timeout` のノードを、
generic action や marker comment に潰さず、
deterministic な runtime semantics へ落とす最小設計を定義する。

対象は「自然言語から timeout を推定する」ことではなく、
explicit metadata がある timeout wrapper を
`IRGenerator -> IREmitter -> Blueprint -> CodeBuilder`
の各段で同じ構造として保持することである。

## 2. Metadata Contract

`WRAP/timeout` は次の metadata を持つ。

- `wrapper_kind = "timeout"`
- `timeout_ms = int`
- `timeout_resolution = "explicit_timeout_ms" | "default_timeout_ms"`
- `body = [...]`

`timeout_ms` は次の順で決める。

1. explicit `timeout_ms`
2. explicit `max_duration_ms`
3. explicit `duration_ms`
4. どれも無い場合は `30000`

`30000` は downstream の暗黙既定ではなく、
`timeout_resolution=default_timeout_ms` を伴う materialized metadata として残す。

## 3. Promotion Boundary

`timeout` wrapper は lexical surface だけでは昇格させない。

昇格条件は次のどちらかである。

- explicit `wrapper_kind=timeout`
- explicit `timeout_ms/max_duration_ms/duration_ms`

つまり、`retry` のような lexical wrapper 判定は使わず、
timeout だけは explicit metadata first とする。

## 4. Emission Boundary

### 4.1 IREmitter

- `spec_role=WRAP` と `wrapper_kind=timeout` を検出する
- child body を通常どおり再帰 emit する
- emit 済み body を単一の `timeout` statement に再構成する

statement shape:

- `type = "timeout"`
- `timeout_ms = int`
- `timeout_resolution = ...`
- `body = [...]`

### 4.2 CodeBuilder / Fallback Renderer

sync method:

- `Task.Run(() => { body })`
- `.Wait(TimeSpan.FromMilliseconds(timeout_ms))`
- timeout 時は `TimeoutException`

async method:

- `CancellationTokenSource(TimeSpan.FromMilliseconds(timeout_ms))`
- `Task.Run(async () => { body }, timeoutCts.Token)`
- `await timeoutTask.WaitAsync(timeoutCts.Token)`
- timeout 時は `TimeoutException`

## 5. Explicit Non-Goals

今回の最小設計では次を扱わない。

- natural language からの timeout 推定
- timeout exception type の自由推定
- nested body への cancellation token 自動注入
- timeout wrapper と retry wrapper の自動合成

## 6. Validation Target

成功条件は次の 3 点である。

1. `semantic_roles.timeout_ms` と `timeout_resolution` が IR に残る
2. `best_path.statements` に `timeout` statement が残る
3. generated code に sync/async それぞれの timeout guard が現れる
