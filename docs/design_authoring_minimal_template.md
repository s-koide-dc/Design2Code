# Design Authoring Minimal Template

## Document Contract
This document is an `optional_reference_docs` authoring guide.

1. `README.md` is not the place for full authoring templates.
2. [docs/generate_from_design_dataflow.md](/C:/workspace/NLP/docs/generate_from_design_dataflow.md) defines the generation and assist contract.
3. This document shows practical starting shapes for writing a new `.design.md` with the fewest tags that still preserve the current boundary.

## Scope
Use this document when creating a new method-level `.design.md` from scratch and deciding how much explicit metadata to keep.

## Recommended operating rule
Use the following authoring ladder:

1. Start from the deterministic minimal template.
2. Only drop down to the assisted template if you intentionally accept `literal_roles_only` recovery.
3. Do not cross into the prohibited template.

## Example problem
The examples below all describe the same task:

1. Read `users.json`.
2. Convert it into a user list.
3. Filter users whose `Name` starts with `A`.
4. Display the results.

## Template A: Deterministic Minimal
This is the default recommended shape for new authoring today.

```md
# UserNamePrefixSearch
## 1. Purpose
'A'で始まる名前のユーザーを抽出して表示します。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
1. 'users.json' を読み込む
2. データをユーザーリストに変換する
3. 名前が 'A' で始まるユーザーを抽出する
4. 条件に合致したユーザー一覧を表示する
### Test Cases
- **Scenario**: Default
- **Expected**: true
```

Why this is the current default:

1. `step_meta` is omitted.
2. `refs` is omitted.
3. `ops` is omitted.
4. Literal boundary is still preserved through `'users.json'` and `'A'`.
5. Current deterministic inference can usually recover the missing structure from this shape.

## Template B: Assisted Boundary
Use this only when you intentionally accept `3B` literal-role recovery.

```md
# UserNamePrefixSearch
## 1. Purpose
'A'で始まる名前のユーザーを抽出して表示します。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
1. users.json を読み込む
2. データをユーザーリストに変換する
3. 名前が A で始まるユーザーを抽出する
4. 条件に合致したユーザー一覧を表示する
### Test Cases
- **Scenario**: Default
- **Expected**: true
```

Why this is only an assisted boundary:

1. Explicit bracket tags are still omitted.
2. The filename survives in prose, but the quoted literal boundary is weaker.
3. Depending on the task, deterministic inference may still succeed, but this is closer to the edge.
4. If deterministic inference blocks with `NO_CANDIDATE` while explicit literal candidates still survive, `literal_roles_only` assist is a valid recovery path.

## Template C: Prohibited Boundary
Do not use this as a normal design authoring shape.

```md
# UserNamePrefixSearch
## 1. Purpose
条件に合うユーザーを抽出して表示します。
## 2. Structured Specification
### Input
- **Description**: None
- **Type/Format**: void
### Output
- **Description**: status
- **Type/Format**: bool
### Core Logic
1. データを読み込む
2. ユーザー一覧に変換する
3. 条件に合うユーザーを抽出する
4. 一覧を表示する
### Test Cases
- **Scenario**: Default
- **Expected**: true
```

Why this is prohibited:

1. The file source is no longer explicit.
2. The filter condition is no longer explicit.
3. Recovery would require guessing, not role restoration.
4. This is a design-authoring gap, not an assist target.

## How to verify a new design
For a new module draft, check the reduction boundary with:

```bash
python scripts/probe_design_authoring_reduction.py --design path/to/NewModule.design.md
```

If you are intentionally evaluating the assist boundary:

```bash
python scripts/probe_design_authoring_reduction.py --design path/to/NewModule.design.md --assist-endpoint-url http://127.0.0.1:1234/v1/chat/completions
```

Interpret the result like this:

1. `drop_step_meta_refs_ops` passing deterministically means the draft is already compact enough.
2. `strip_tags_keep_literals` blocking but recovering with assist means you are at the assisted boundary.
3. `strip_tags_drop_literals` blocking means the design text itself must be strengthened.

For a pass/fail check before normal generation, use:

```bash
python scripts/validate_design_authoring.py --design path/to/NewModule.design.md
```

This validator currently checks:

1. `original` must remain valid.
2. `drop_step_meta` must remain deterministic.
3. `drop_step_meta_refs` must remain deterministic.
4. `drop_step_meta_refs_ops` must remain deterministic.
5. `strip_tags_drop_literals` must fail with deterministic `NO_CANDIDATE`.

Optional assist-aware validation:

```bash
python scripts/validate_design_authoring.py --design path/to/NewModule.design.md --assist-endpoint-url http://127.0.0.1:1234/v1/chat/completions
```

In that mode, the validator still keeps deterministic generation primary. It only adds observations about whether `strip_tags_keep_literals` can recover under the current `literal_roles_only` contract.

After the draft passes the authoring gate, inspect the actual generated code as well:

```bash
python scripts/review_design_generation_snapshot.py --design path/to/NewModule.design.md
```

This review step is the place to confirm:

1. The inferred design is still faithful to the draft.
2. The final `.cs` reflects the intended data flow.
3. `SpecAuditor` issues and compile verification are acceptable.
4. Tag reduction did not merely move ambiguity downstream into weak generated code.

## Practical guidance
When the goal is to reduce tagging effort without increasing LLM dependence:

1. Delete `step_meta` first.
2. Then delete `refs`.
3. Then delete `ops` only if the natural-language step still pins the operation clearly.
4. Keep explicit `path` / `url` / `sql` boundaries as long as possible.
5. If you feel pressure to remove the literal boundary, use the probe first instead of assuming the model will recover it.

## Current verified minimal examples
The following scenarios currently pass both the authoring gate and the generation snapshot review:

1. File path flow: [scenarios/UserNamePrefixSearch.design.md](/C:/workspace/NLP/scenarios/UserNamePrefixSearch.design.md)
2. DB query flow: [scenarios/InventoryLookupMinimal.design.md](/C:/workspace/NLP/scenarios/InventoryLookupMinimal.design.md)
3. HTTP fetch flow: [scenarios/ProductApiLookupMinimal.design.md](/C:/workspace/NLP/scenarios/ProductApiLookupMinimal.design.md)
4. Environment fetch flow: [scenarios/AppModeEchoMinimal.design.md](/C:/workspace/NLP/scenarios/AppModeEchoMinimal.design.md)

What these examples mean in practice:

1. File tasks can stay minimal if the path literal remains explicit in prose.
2. DB tasks can stay minimal if the SQL literal remains explicit in prose or `semantic_roles.sql`.
3. HTTP tasks can stay minimal if the URL literal remains explicit in prose or `semantic_roles.url`.
4. Env tasks can stay minimal if the `env` data source remains explicit and the fetch step still names the environment variable.
