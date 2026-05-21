# Wrap Retry Semantics Design

## 1. Purpose

この文書は、`spec_role=WRAP` かつ `wrapper_kind=retry` のノードを、marker comment ではなく deterministic な codegen semantics へ落とすための最小設計を定義する。

目的は「何となく retry らしい文字列を出す」ことではなく、`IREmitter -> Blueprint -> CodeBuilder` の各段で同じ構造を保持することである。

## 2. Design Decision

`WRAP/retry` は runtime role へ潰さず、専用 statement type `retry` として保持する。

この statement は最低限次の形を持つ。

- `type = "retry"`
- `body = [...]`
- `max_attempts = int`
- `max_attempts_resolution = "explicit_attempts" | "token_attempts" | "default_attempts"`
- `exception_type = "Exception"`
- `exception_type_resolution = "explicit_exception_type" | "default_exception_type"`
- `base_delay_ms = int` (optional)
- `max_delay_ms = int` (optional)
- `backoff_multiplier = float` (optional)
- `retry_delay_policy_resolution = "explicit_delay_policy" | "default_no_delay_policy"`

`body` は wrapper の child body をそのまま保持する。

`max_attempts` は explicit metadata を優先し、retry step の token sequence に `<number> + 回` がある場合に限って補完する。  
それでも決まらない場合は `3` を materialize し、`max_attempts_resolution=default_attempts` を付ける。  
`exception_type` は explicit metadata のみ受け付け、無い場合は `Exception` と `exception_type_resolution=default_exception_type` を付ける。  
delay/backoff 系 (`base_delay_ms`, `max_delay_ms`, `backoff_multiplier`) も explicit metadata のみ受け付け、無い場合は `base_delay_ms=0`, `backoff_multiplier=1.0`, `retry_delay_policy_resolution=default_no_delay_policy` を付ける。

## 3. Emission Boundary

### 3.1 IREmitter

- `spec_role=WRAP` を検出する
- child body を通常どおり再帰 emit する
- emit 済みの child statement 群を平坦化したまま残さず、単一の `retry` statement に再構成する

### 3.2 Blueprint / CodeBuilder

- `retry` statement は blueprint 上の正式 statement type とする
- fallback renderer と C# CodeBuilder の両方が同じ semantics を解釈する

### 3.3 Generated C#

初期の canonical form は次の構造とする。

```csharp
for (var retryAttempt = 0; retryAttempt < N; retryAttempt++)
{
    try
    {
        // body
        break;
    }
    catch (Exception)
    {
        if (retryAttempt == N - 1) throw;
    }
}
```

これは retry budget と rethrow 境界だけを deterministic に表現する最小形である。

delay metadata がある場合は、sync method では `System.Threading.Thread.Sleep(retryDelayMs)`、async method では `await Task.Delay(retryDelayMs)` を使い、必要なら `Math.Min` と `Math.Ceiling` で次回 delay を更新する。

## 4. Why This Shape

この形を採る理由は次の通りである。

1. marker comment より強い semantics を持てる  
2. raw code 注入より builder/fallback の整合を保ちやすい  
3. 将来 `backoff`, `exception narrowing`, `retry options` を metadata 追加で拡張しやすい  

## 5. Explicit Non-Goals

今回の最小設計では次を扱わない。

- explicit metadata を伴わない exception class の推定
- explicit metadata を伴わない delay/backoff policy の推定
- retry 回数の自然言語からの高度推定

## 6. Default Policy

- `max_attempts` は metadata が無い場合 `3`
- `exception_type` は metadata が無い場合 `Exception`
- `base_delay_ms` は metadata が無い場合 `0`
- `backoff_multiplier` は metadata が無い場合 `1.0`

この default は downstream の暗黙既定ではなく、`*_resolution` を伴う IR / statement metadata として materialize される。  
目的は「semantic gap を埋める最小値」を観測可能にすることであり、wrapper metadata が richer になれば置き換え可能である。

## 7. Validation Target

成功条件は次の 3 点である。

1. `best_path.statements` に `retry` statement が残る  
2. generated code に `for + try/catch + break/rethrow` が現れる  
3. wrapper body が generic fallback action に落ちない  
