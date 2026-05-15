# ReturnResolution Design Document

## 1. Purpose

`return_resolution` は、`spec_role=RETURN` の node に対して
literal return metadata を決定論的に正規化する helper module である。

対象は `return_value`, `return_value_resolution`, `return_source_node_id` であり、
自然言語から過剰な意味推定は行わず、
explicit metadata、quoted literal、token 上の `true/false/null`、
および text 中の先頭 numeric literal だけを扱う。

## 2. Structured Specification

### Input
- `step_text`: 元の step 文
- `tokens`: 形態素トークン列
- `semantic_roles`: step 側または分析側の `semantic_roles`

### Output
- literal return metadata を補完した `semantic_roles`

### Core Logic
1. explicit `source_var` がある場合はそれを `return_value` に正規化し、`source_var` resolution を付与する。
2. explicit `return_value` がある場合はそれを優先し、`return_value_resolution` を正規化する。
3. quoted literal があれば `quoted_literal` として保持する。
4. token 上に `null` があれば `literal_null` とする。
5. token 上に `true/false` があれば `literal_boolean` とする。
6. text 中に numeric literal があれば `literal_numeric` とする。
7. literal でなく `input_link` がある場合は `return_source_node_id` と `input_link_var` を付与する。
   - `input_link` が `CHECK` のような structural parent を指す場合は、その node 自体ではなく upstream semantic source を保持する。
8. 上記に該当しない場合は metadata を追加しない。

### Test Cases
- **Happy Path**:
  - `true を返す`
  - 出力に `return_value=true`, `return_value_resolution=literal_boolean`
- **Edge Cases**:
  - `null を返す`
  - 出力に `return_value=null`, `return_value_resolution=literal_null`
  - `「done」を返す`
  - 出力に `return_value=done`, `return_value_resolution=quoted_literal`
  - `取得したユーザーを返す`
  - 出力に `return_source_node_id=<upstream id>`, `return_value_resolution=input_link_var`

## 3. Boundary Rules

- success/failure のような意味語から boolean を推定しない
- regex-based free text parsing はしない
- variable return と literal return を混同しない
- upstream source の特定は `input_link` に限定し、自然言語から変数名を推測しない

## 4. Consumers

- `src.ir_generator.ir_generator.IRGenerator`
- `src.code_synthesis.action_synthesizer.ActionSynthesizer`
