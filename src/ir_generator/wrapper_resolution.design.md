# WrapperResolution Design Document

## 1. Purpose

`wrapper_resolution` は、`spec_role=WRAP` の node に対して、wrapper kind ごとの最小 metadata を決定論的に整える helper module である。

現在の対象は `retry`, explicit `timeout`, explicit `transaction` である。

- `retry`: `max_attempts`, `exception_type`, `base_delay_ms`, `max_delay_ms`, `backoff_multiplier` と、それらの provenance (`max_attempts_resolution`, `exception_type_resolution`, `retry_delay_policy_resolution`)
- `timeout`: `timeout_ms` と provenance (`timeout_resolution`)
- `transaction`: `transaction_resolution`

自然言語から過剰な推測を行わず、explicit metadata と token sequence、明示 default policy だけを扱う。

## 2. Structured Specification

### Input
- `tokens`: 形態素トークン列
- `semantic_roles`: step 側または分析側の `semantic_roles`

### Output
- wrapper metadata を補完した `semantic_roles`

### Core Logic
1. `wrapper_kind` と `structure_kind` の default を整える。
2. wrapper kind は次の順で決める。
   - explicit `wrapper_kind`
   - retry metadata の存在
   - retry lexical surface/token
   - どれでもなければ `wrapper` のまま保持
3. `wrapper_kind=retry` のとき、retry 回数は次の優先順で決める。
   - explicit `max_attempts`
   - explicit `max_retries`
   - explicit `retry_count`
   - token sequence 上の `<number> + 回`
   - どれも無い場合は `max_attempts=3` を materialize し、`max_attempts_resolution=default_attempts` を付ける。
4. `wrapper_kind=retry` の exception type は explicit metadata のみ受け付け、無い場合は `exception_type=Exception` と `exception_type_resolution=default_exception_type` を付ける。
5. `wrapper_kind=retry` の delay/backoff 系は explicit metadata のみ受け付け、無い場合は `base_delay_ms=0`, `backoff_multiplier=1.0`, `retry_delay_policy_resolution=default_no_delay_policy` を付ける。
6. `wrapper_kind=timeout` の timeout budget は次の優先順で決める。
   - explicit `timeout_ms`
   - explicit `max_duration_ms`
   - explicit `duration_ms`
   - どれも無い場合は `timeout_ms=30000` を materialize し、`timeout_resolution=default_timeout_ms` を付ける。
7. `wrapper_kind=transaction` の場合は `transaction_resolution=explicit_transaction_wrapper` を付ける。
8. 値が不正でも停止せず、deterministic に materialize できた metadata だけを返す。

### Test Cases
- **Happy Path**:
  - explicit `max_attempts=5`
  - 出力に `max_attempts=5`
- **Edge Cases**:
  - `3 回再試行` の token 列
  - 出力に `max_attempts=3`
  - metadata を持たない `retry`
  - 出力に `max_attempts=3`, `exception_type=Exception`, `retry_delay_policy_resolution=default_no_delay_policy`
  - explicit `wrapper_kind=timeout`, `timeout_ms=5000`
  - 出力に `wrapper_kind=timeout`, `timeout_resolution=explicit_timeout_ms`
  - metadata を持たない `timeout`
  - 出力に `timeout_ms=30000`, `timeout_resolution=default_timeout_ms`
  - explicit `wrapper_kind=transaction`
  - 出力に `transaction_resolution=explicit_transaction_wrapper`
  - invalid `max_attempts`
  - token 由来または未設定へ fallback

## 3. Boundary Rules

- keyword-based exception inference はしない
- regex-based free text extraction はしない
- retry metadata が無い場合でも downstream default に丸投げせず、default policy metadata を IR 側で materialize する
- timeout wrapper は lexical surface だけでは昇格させず、explicit metadata (`wrapper_kind` / `timeout_ms`) がある場合だけ deterministic に扱う
- transaction wrapper も lexical surface だけでは昇格させず、explicit `wrapper_kind=transaction` がある場合だけ deterministic に扱う

## 4. Consumers

- `src.ir_generator.ir_generator.IRGenerator`
