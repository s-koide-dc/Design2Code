# Wrap Transaction Semantics Design

## 1. Purpose

この文書は、`spec_role=WRAP` かつ explicit `wrapper_kind=transaction` のノードを、
generic action に潰さず deterministic な transaction semantics へ落とす最小設計を定義する。

対象は transaction を自然言語から推定することではなく、
explicit wrapper metadata を `IR -> Blueprint -> CodeBuilder` まで保つことである。

## 2. Metadata Contract

`WRAP/transaction` は次を持つ。

- `wrapper_kind = "transaction"`
- `transaction_resolution = "explicit_transaction_wrapper"`
- `body = [...]`

現段階では isolation level や transaction option の自然言語推定は扱わない。

## 3. Promotion Boundary

`transaction` wrapper は lexical surface だけでは昇格させない。

昇格条件:

- explicit `wrapper_kind=transaction`

つまり transaction は explicit metadata first で扱う。

## 4. Emission Boundary

### 4.1 IREmitter

- `spec_role=WRAP` と `wrapper_kind=transaction` を検出する
- child body を再帰 emit する
- emit 済み body を単一の `transaction` statement に再構成する

### 4.2 CodeBuilder / Fallback Renderer

sync method:

- `using var transactionScope = new System.Transactions.TransactionScope();`
- `body`
- `transactionScope.Complete();`

async method:

- `using var transactionScope = new System.Transactions.TransactionScope(System.Transactions.TransactionScopeAsyncFlowOption.Enabled);`
- `body`
- `transactionScope.Complete();`

## 5. Explicit Non-Goals

- transaction lexical inference
- isolation level / timeout / nested option inference
- database transaction API への環境依存な切替

## 6. Validation Target

1. `transaction_resolution` が IR に残る
2. `best_path.statements` に `transaction` statement が残る
3. sync/async codegen に `TransactionScope` と `Complete()` が現れる
