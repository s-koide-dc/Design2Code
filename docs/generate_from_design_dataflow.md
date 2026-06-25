# generate_from_design dataflow (method-level)

## Document Contract
This document is a `required_docs` generation-flow reference managed by `config/doc_reference_policy.json`.

1. README is responsible for the public entrypoint summary and verified usage examples.
2. This document is responsible for the deeper method-level flow, verification steps, and inference / replanning boundaries behind `scripts/generate/generate_from_design.py`.
3. When the generate pipeline, verification stages, or entrypoint flags change, update this document together with `README.md` and re-run `scripts/validate_project_consistency.py`.

## Scope
This document covers the data flow triggered by `scripts/generate/generate_from_design.py` and the concrete methods it calls directly or indirectly during the design-to-code pipeline.

## High-level flow summary
### Single-module mode (default)
1. Read a `.design.md` file and parse it into a StructuredSpec.
2. Optionally ask a local OpenAI-compatible backend for `literal_roles_only` suggestions (`path` / `url` / `sql`) and apply only accepted suggestions in-memory.
3. Validate the StructuredSpec.
4. Enforce safety policy and project rules.
5. Convert the StructuredSpec into an IR tree.
6. Synthesize C# code via blueprint emission and CodeBuilder.
7. Run SpecAuditor and optional replanning retries.
8. Verify compilation in a sandbox.
9. Optionally run execution verification.
10. Write the final `.cs` output file.
11. Review one scenario with `scripts/review_design_generation_snapshot.py` or run curated regression checks with `scripts/run_design_generation_regression.py`.

### Project mode (`--project`)
1. Read a project `.design.md` file and parse it into a ProjectSpec.
2. Enforce project rules.
3. Generate the multi-file project via `ProjectGenerator`.
4. Optionally audit method specs via SpecAuditor/Replanner.
5. Optionally run C# analysis or refactoring analysis.
6. Verify compilation of the generated project.

## Infer-Then-Freeze Policy (Design Spec Inference)
This flow applies when a design spec omits explicit metadata and the system performs deterministic inference once, then persists the inferred metadata into a sibling `.inferred.design.md` before generation.

1. Parse the raw `.design.md` into a preliminary StructuredSpec.
2. Optionally apply accepted LLM literal-role suggestions (`semantic_roles.path/url/sql`) in-memory, while leaving the original `.design.md` unchanged.
3. Detect missing explicit metadata in Core Logic (`ops`, `semantic_roles`, `data_source`, `refs`).
4. Run deterministic inference using fixed assets and scoring rules to propose metadata.
5. Persist the inferred metadata into `.inferred.design.md` while leaving the original `.design.md` unchanged.
6. Re-parse the generated `.inferred.design.md` and continue the standard generation flow.
7. Record the asset versions used for inference in logs or design metadata to ensure traceability.

## Implementation Placement (Recommended)
1. `scripts/generate/generate_from_design.py:main`
   - After reading the `.design.md` but before strict validation, run inference if missing metadata is detected.
   - If `--assist-literal-tags-http` is enabled with `--assist-policy always`, call the local HTTP backend first and pass only accepted `literal_roles_only` suggestions into inference.
   - If `--assist-policy on_blocked_only` is used, retry with the local HTTP backend only after deterministic inference returns `blocked` with at least one `NO_CANDIDATE` issue.
   - Emit inferred tags and the `### Inference Metadata` block into `.inferred.design.md`.
   - Re-parse that inferred file and then run `validate_structured_spec_or_raise`.
2. `src/design_parser/structured_parser.py`
   - Remains deterministic and metadata-driven; it does not perform inference.
3. `src/design_parser/design_inference.py`
   - Preferred location for deterministic inference rules, fingerprint generation, and `.inferred.design.md` write-out.
4. `src/utils/design_sync_util.py`
   - Optional helper for targeted step updates (used only if required by refiner).

## Inference Rules (Deterministic)
1. Inference is only allowed when explicit metadata is missing.
2. Inference must never overwrite explicit `[KIND|...]`, `[ops:...]`, `[semantic_roles:{...}]`, `[data_source|...]`, or `[refs:...]`.
3. Inference must use fixed assets and fixed scoring rules. No randomness is permitted.
4. If confidence is below the configured threshold, inference must not insert metadata and must instead emit a blocking issue.
5. The output of inference must be stable for identical inputs under identical asset versions.
6. Optional LLM assistance may only add accepted explicit literal roles (`path` / `url` / `sql`) and must not overwrite explicit user-authored tags.

## Inference Scope (What Can Be Filled)
Inference is limited to the following missing elements:
1. Step metadata: `KIND`, `INTENT`, `TARGET`, `OUTPUT`, `SIDE_EFFECT`.
2. `refs` (input dependencies) when a step is missing explicit refs.
3. `data_source` declarations for steps that clearly reference a known store or path.
4. `semantic_roles` for:
   - `DATABASE_QUERY` / `PERSIST` → `semantic_roles.sql` (only if SQL is explicitly present in text).
   - `HTTP_REQUEST` → `semantic_roles.url` (only if URL is explicitly present in text).
   - `CMD_RUN` → `semantic_roles.command` (only if command text is explicitly present in text and the base command is allowed by `config/safety_policy.json`).
5. `source_kind` when `source_ref` is inferred and a valid data source is present.
6. Literal boundary:
   - `path` / `url` / `sql` are not guessed from vague prose.
   - If a design omits those explicit literals, deterministic inference may block and validation should fail instead of inventing values.

## Authoring Reduction Policy
When writing a new `.design.md`, the current recommended reduction policy is:
1. `Required`
   - Explicit literal boundary data: `semantic_roles.path`, `semantic_roles.url`, `semantic_roles.sql`, or equivalent surviving literal text that deterministic/assisted flow can anchor to.
   - If removing the literal would make the step ambiguous, keep it.
2. `Recommended`
   - Important `data_source` declarations, especially for HTTP / DB / file-backed flows.
   - Keep these when source identity matters for readability or when multiple sources coexist.
3. `Omittable under deterministic inference`
   - Many `step_meta` tags.
   - Some `refs`.
   - Some `ops`.
   - Some plain source description tags when the description is already deterministic enough.
4. `Omittable only with 3B assistance`
   - Literal-bearing `path` / `url` / `sql` tags that are intentionally dropped and later recovered through `literal_roles_only`.
   - This is an assisted authoring mode, not a pure deterministic contract.

Practical authoring order:
1. Reduce `step_meta` first.
2. Then reduce `refs` / `ops` / `data_source` where readability remains acceptable.
3. Keep literal boundaries (`path` / `url` / `sql`) unless you are intentionally relying on the `3B` assist path.

## Literal Assist Acceptance Contract
`literal_roles_only` assistance is not a general semantic completion feature. It is a narrowly scoped recovery path for explicit literal boundaries that already exist in the design text.

### What the assist is allowed to do
1. Add only missing `semantic_roles.path`, `semantic_roles.url`, or `semantic_roles.sql`.
2. Copy only explicit literals already present in the original line.
3. Apply suggestions only in-memory before deterministic inference.
4. Leave the original `.design.md` unchanged.
5. Record accepted application in `.inferred.design.md` through `llm_literal_assist:*` metadata.

### What the assist is not allowed to do
1. Invent file paths, URLs, or SQL that are not explicitly present in the original line.
2. Add or rewrite `step_meta`.
3. Add or rewrite `refs`.
4. Overwrite an explicit existing `semantic_roles` value.
5. Expand vague prose such as "API から取得する" into a guessed endpoint.
6. Turn a design-authoring gap into an LLM-dependent implicit contract.

### Candidate selection boundary
`scripts/suggest_design_tags.py` should only query candidates that satisfy all of the following:
1. The step is a Core Logic step, not a `data_source` declaration.
2. The step is missing `semantic_roles`.
3. The step still contains an explicit literal signal that can anchor `path`, `url`, or `sql`.
4. Priority is given to literal-bearing candidates; if none exist, broader completion is not the default recovery path for this mode.

Explicit literal signals currently mean one of:
1. A quoted filename-like literal such as `'users.json'`.
2. An explicit URL such as `https://api.example.com/...`.
3. An explicit SQL literal that already appears in the line.

### Acceptance checks
A returned suggestion is accepted only when all of the following hold:
1. `step_number` matches an actual candidate step.
2. `semantic_roles` is a JSON object.
3. `path` exactly matches the quoted filename-like literal in the original line.
4. `url` exactly matches one of the URLs present in the original line.
5. `sql` exactly matches the SQL literal present in the original line.
6. In `literal_roles_only` mode, no `step_meta` is returned.
7. In `literal_roles_only` mode, no `refs` are returned.
8. The suggestion is not a noop; at least one accepted `path` / `url` / `sql` value is present when the candidate was missing literal roles.

### Rejection classes
The current rejection reasons are operationally important because they define the trust boundary:
1. `unknown_step_number`
2. `semantic_roles_must_be_object`
3. `path_literal_not_explicit_in_original_line`
4. `url_literal_not_explicit_in_original_line`
5. `sql_literal_not_explicit_in_original_line`
6. `refs_not_allowed_in_literal_roles_only`
7. `step_meta_not_allowed_in_literal_roles_only`
8. `noop_suggestion`
9. `literal_candidate_requires_path_or_url_or_sql`

Interpretation:
1. If rejection is caused by invented or mismatched literals, the model is outside the allowed contract and the suggestion must be discarded.
2. If rejection is caused by noop output, the design should be treated as unresolved rather than partially trusted.
3. If no acceptable suggestion exists, deterministic blocking remains the correct outcome.

### Invocation policy
`generate_from_design.py` currently supports two invocation policies:
1. `on_blocked_only`
   - Default.
   - Call the assist only after deterministic inference returns `blocked` with at least one `NO_CANDIDATE` issue.
   - This is the preferred operational mode because it keeps deterministic generation primary.
2. `always`
   - Query the assist before inference.
   - Use only when intentionally researching authoring reduction or comparing assisted vs deterministic behavior.

### Operational decision rule
Use `literal_roles_only` assistance when all of the following are true:
1. Deterministic generation is still the primary contract.
2. The blocked step retains an explicit `path` / `url` / `sql` literal.
3. The missing information is only the literal role tag, not the underlying design meaning.
4. The accepted result can be traced in `.inferred.design.md`.

Do not use `literal_roles_only` assistance as the main remedy when any of the following are true:
1. The design text itself is ambiguous.
2. The step lacks an explicit literal anchor.
3. The missing information is about control flow, dependencies, or operation meaning rather than literal roles.
4. Recovery would require guessed endpoints, guessed SQL, or guessed file locations.

## Authoring Reduction Probe
To compare how far a new `.design.md` can be reduced before crossing the literal boundary, use:

```bash
python scripts/probe_design_authoring_reduction.py --design path/to/NewModule.design.md
```

The current stages are:
1. `original`
2. `drop_step_meta`
3. `drop_step_meta_refs`
4. `drop_step_meta_refs_ops`
5. `strip_tags_keep_literals`
6. `strip_tags_drop_literals`

Interpretation:
1. If `drop_step_meta_refs_ops` still passes deterministically, the design is already compact enough without LLM help.
2. If `strip_tags_keep_literals` blocks but `literal_roles_only` assist recovers it, that is an assisted authoring boundary rather than a deterministic one.
3. If `strip_tags_drop_literals` still blocks even with assist, the design has crossed the explicit literal boundary and should be rewritten, not patched with broader LLM dependence.

To compare the same stages with optional `3B` literal assistance:

```bash
python scripts/probe_design_authoring_reduction.py --design path/to/NewModule.design.md --assist-endpoint-url http://127.0.0.1:1234/v1/chat/completions
```

For a practical starter shape and a prohibited over-reduced shape, see [docs/design_authoring_minimal_template.md](/C:/workspace/NLP/docs/design_authoring_minimal_template.md).

For a pass/fail authoring gate before normal generation, use:

```bash
python scripts/validate_design_authoring.py --design path/to/NewModule.design.md
```

To review the same design as original text, inferred design, and generated code in one pass, use:

```bash
python scripts/review_design_generation_snapshot.py --design path/to/NewModule.design.md
```

To run the current curated regression set with the same snapshot criteria, use:

```bash
python scripts/run_design_generation_regression.py
```

Notes:
1. The current default regression set is `ComplexLinqSearch`, `CsvSalesAggregation`, `DailyInventorySync`, `SecureOrderProcessing`, and `AppModeEchoMinimal`.
2. Use repeated `--design` flags to replace the default set with a narrower or experimental set.
3. The regression runner aggregates `inference_status`, `verification_valid`, `spec_issue_count`, and the full per-scenario snapshot payload into one JSON result.

## Current Assist Coverage Snapshot (2026-06-18)
The current scenario inventory from `scripts/audit_literal_tag_assist_coverage.py` is:
1. Total `.design.md` scenarios audited: `23`
2. `blocked_no_candidate`: `14`
3. `assist_recommended`: `11`

Current `on_blocked_only` assist candidates:
1. `AggregationSummary`
2. `BatchProcessProducts`
3. `DailyInventorySync`
4. `EnvConfigToConsole`
5. `EphemeralCalculation`
6. `FetchProductInventory`
7. `InferThenFreezeMinimal`
8. `InputLinkDropRepro`
9. `RobustConfigLoader`
10. `StateUpdatePersist`
11. `UserReportGenerator`

Blocked cases that should be treated primarily as design-authoring gaps rather than literal-assist targets:
1. `CalculateOrderDiscount`
2. `CsvSalesAggregation`
3. `SecureOrderProcessing`

Interpretation:
1. If a blocked stripped design still retains explicit `path` / `url` / `sql` candidates, `literal_roles_only` is a reasonable recovery path.
2. If a blocked stripped design has no useful literal candidates, the next action should be to strengthen the design text itself, not to broaden LLM dependence.

## Inference Order (Deterministic)
1. Identify explicit tags and lock them.
2. Infer `data_source` candidates and `source_kind`.
3. Infer step `KIND/INTENT/TARGET/OUTPUT/SIDE_EFFECT`.
4. Infer `refs` based on nearest previous step with compatible output.
5. Infer `semantic_roles` from explicit literals in the line (URL/SQL/command).
6. Recompute a normalized line with the inferred tags and persist to `.inferred.design.md`.

## Confidence Thresholds and Blocking Rules
1. Each inferred field must exceed its configured confidence threshold.
2. If any required field fails thresholding, inference must stop and emit a blocking issue.
3. Blocking issues must prevent code generation until the `.design.md` is fixed.
4. Minimal thresholds (defaults; can be overridden in config):
   - `intent_threshold`: 0.80
   - `entity_threshold`: 0.80
   - `data_source_threshold`: 0.85
   - `refs_threshold`: 0.75
5. If explicit literals are missing for `semantic_roles` (SQL/URL/command), the field must not be inferred.
6. Validation must also reject:
   - `HTTP_REQUEST` without `semantic_roles.url` and `source_ref(kind=http)`.
   - DB-backed `PERSIST` / `DATABASE_QUERY` without `semantic_roles.sql`.
   - file-backed `FETCH` without either `source_ref(kind=file)` or `semantic_roles.path`.

## Inference Output Format (Design Doc Embedding)
Insert inferred metadata directly into the existing Core Logic lines using the standard bracket tags.
Example (inferred tags are still standard tags, not a new syntax):
`[ACTION|FETCH|User|List<User>|NONE|user_db|db] [ops:aggregate_by_product] [semantic_roles:{"sql":"SELECT ..."}] ...`

Add a single traceability block near the top of the design doc (e.g., after Purpose) when inference is used:
```
### Inference Metadata
- inference_mode: infer_then_freeze
- inference_fingerprint: <sha256 of normalized design + asset versions>
- assets:
  - vector_model_path: <path>
  - dictionary_path: <path>
  - scoring_rules_path: <path>
  - method_store_path: <path>
- llm_literal_assist: true|false
- llm_literal_assist_mode: literal_roles_only
- llm_literal_assist_provider: openai_compatible_http
- llm_literal_assist_model_id: qwen2.5-3b-instruct
- llm_literal_assist_applied_steps: 1, 3
```
Notes:
1. Do not include timestamps in the design doc to preserve deterministic output.
2. The fingerprint must be reproducible from normalized inputs and asset versions.
3. `llm_literal_assist_*` fields are omitted when assistance is not used or when no accepted suggestion is applied.

## Fingerprint Calculation (Deterministic)
The fingerprint is a SHA-256 of a normalized payload. The payload is a JSON string with fixed ordering and no whitespace variance.

1. `design_text_normalized`:
   - Normalize line endings to `\n`.
   - Trim trailing whitespace on each line.
   - Remove an existing `### Inference Metadata` block if present.
2. `assets`:
   - `vector_model_path`
   - `dictionary_path`
   - `scoring_rules_path`
   - `method_store_path`
   - `config_paths` (config.json, safety_policy.json, project_rules.json, retry_rules.json)
3. `asset_versions`:
   - For each asset path, compute `{ path, size_bytes, sha256 }`.
4. `payload`:
   - `{ design_text_normalized, asset_versions, inference_rules_version }`
   - `inference_rules_version` is a fixed string (e.g., `v1`) updated only when rules change.

The fingerprint is `sha256(json(payload))`, with keys sorted and UTF-8 encoding.

## Method-level data flow

### 1. `scripts/generate/generate_from_design.py:main`
Inputs
1. CLI args `--design`, `--output`, `--retry`.
2. Optional mode flags: `--project`, `--project-audit-only`, `--no-project-audit`, `--allow-unsafe`, `--strict-semantics`, `--allow-fallback`, `--post-exec-verify`, `--post-csharp-analyze`, `--post-refactor-analyze`, `--assist-literal-tags-http`, `--assist-endpoint-url`, `--assist-model-id`, `--assist-timeout-seconds`, `--assist-max-new-tokens`, `--assist-policy`.

Flow
1. Validate that the design file exists.
2. Build core objects: `ConfigManager`, `MethodStore`, `VectorEngine`, `StructuredDesignParser`, `ProjectSpecParser`, `CodeSynthesizer`, `CompilationVerifier`, `ExecutionVerifier`, `Replanner`, `NuGetClient`, `SpecAuditor`.
3. If `--project-audit-only` is set:
   1. Parse a ProjectSpec via `ProjectSpecParser.parse_file`.
   2. Audit project methods via `audit_project_methods` (uses SpecAuditor + Replanner).
   3. Exit.
4. If `--project` is set:
   1. Parse a ProjectSpec via `ProjectSpecParser.parse_file`.
   2. Enforce project rules for design path.
   3. Generate the multi-file project via `ProjectGenerator.generate`.
   4. Optionally run SpecAuditor/Replanner (`audit_project_methods`) unless `--no-project-audit`.
   5. Optionally run C# analysis or refactoring analysis.
   6. Verify compilation via `CompilationVerifier.verify_project`.
   7. Print output root path and exit.
5. Otherwise (single-module):
   1. If `--assist-policy always` is selected, call `scripts.suggest_design_tags` helpers in `literal_roles_only` mode before inference.
   2. Run `infer_then_freeze_if_needed`, passing any accepted literal-role suggestions into `DesignInferenceEngine`.
   3. If inference returns `blocked` with `NO_CANDIDATE` and `--assist-policy on_blocked_only` is selected, query literal-tag assistance and retry `infer_then_freeze_if_needed`.
   4. Parse the resulting `.inferred.design.md` via `StructuredDesignParser.parse_design_file`.
   5. Validate the resulting StructuredSpec.
   6. Enforce safety policy unless `--allow-unsafe`.
   7. Enforce project rules (design path, output path, banned patterns).
   8. Synthesize code using `synthesize_structured_spec` (SpecAuditor + optional replanning).
   9. Optionally run execution verification (`ExecutionVerifier`) when `--post-exec-verify` is set.
10. Write the final code to `output_path`.
   11. Recommended follow-up:
      - `scripts/review_design_generation_snapshot.py` for one scenario
      - `scripts/run_design_generation_regression.py` for the curated multi-scenario guardrail

Outputs
1. `.cs` file written to `output_path`.
2. Console logs for progress and errors.

Side effects
1. Compilation sandbox directories under `cache/` (via `CompilationVerifier`).
2. Blueprint JSON written under `cache/blueprints/<run_id>/blueprint.json` (via `CodeBuilderClient`).

### 2. `src/config/config_manager.py:ConfigManager.__init__`
Inputs
1. Optional `workspace_root` (defaults to `os.getcwd()`).

Flow
1. Load multiple JSON configs (`config.json`, `safety_policy.json`, `retry_rules.json`, `project_rules.json`, `scoring_rules.json`, `user_preferences.json`).
2. Build path fields for config and data assets.

Outputs
1. A config object with loaded dictionaries and path fields.

### 2.1 `src/code_generation/project_generator.py:ProjectGenerator.generate`
Inputs
1. Parsed ProjectSpec and `output_root`.

Flow
1. Normalize/complete method specs via `SpecCompletionHelper`.
2. Resolve ops and logic hints via `DesignOpsResolver`, `LogicAuditor`, and `DesignDocRefiner`.
   - Completion is deterministic under fixed dictionaries/models/scoring rules.
3. Generate services/repositories/controllers via helper modules:
   1. `RepoGenerationHelper` (repo methods and SQL paths).
   2. `ServiceGenerationHelper` (service method bodies, optional freeform when `USE_SERVICE_FREEFORM=1`).
   3. `ControllerGenerationHelper` (controller action bodies).
4. Render files using `renderers/` and templates.
5. Generate tests via `TestGenerator`.
6. Emit audit warnings from `AuditHelpers` (logic alignment and design-doc checks).

Outputs
1. Multi-file C# project under `output_root`.

### 3. `src/design_parser/structured_parser.py:StructuredDesignParser.parse_design_file`
Inputs
1. `file_path` to `.design.md`.

Flow
1. Read file contents.
2. Call `parse_markdown`.

Outputs
1. StructuredSpec dictionary.

### 4. `src/design_parser/structured_parser.py:StructuredDesignParser.parse_markdown`
Inputs
1. Raw markdown content.

Flow
1. Use `DesignDocParser.parse_content` to extract purpose, input, output, core logic, test cases.
2. Convert Input and Output sections into structured `inputs` and `outputs`.
3. First pass over core logic to extract `[data_source|...]` declarations.
4. Second pass to convert logic steps into structured steps with:
   1. `id`, `kind`, `intent`, `target_entity`, `output_type`, `side_effect`.
   2. `source_ref` and `source_kind` from metadata if present.
   3. `input_refs` from explicit `[refs:...]` or previous step.
   4. SQL extraction into `semantic_roles.sql` when detected.
5. Resolve source info for steps based on data source declarations.
6. Build test cases list.
7. Validate the final StructuredSpec.

Outputs
1. StructuredSpec dictionary validated via `validate_structured_spec_or_raise`.

### 5. `src/utils/design_doc_parser.py:DesignDocParser.parse_content`
Inputs
1. Markdown content string.

Flow
1. Split content by Markdown headers.
2. Extract:
   1. Module name from H1.
   2. Purpose section.
   3. Input and Output sections.
   4. Core Logic list items.
   5. Test Cases.
3. Normalize into a legacy structure consumed by `StructuredDesignParser`.

Outputs
1. A legacy-structured dictionary with `module_name`, `purpose`, `specification`, `test_cases`.

### 6. `src/code_synthesis/synthesis_pipeline.py:synthesize_structured_spec`
Inputs
1. `method_name`, `structured_spec`.
2. Optional services: `verifier`, `replanner`, `spec_auditor`, `nuget_client`.
3. Retry controls: `allow_retry`, `allow_fallback`, `max_retries`.

Flow
1. Validate structured spec (`validate_structured_spec_or_raise`).
2. Call `CodeSynthesizer.synthesize_from_structured_spec` (IR generation + first pass synthesis).
3. Audit alignment via `SpecAuditor.audit` (if provided).
4. Resolve NuGet dependencies from usings via `resolve_nuget_deps`.
5. Verify compilation via `CompilationVerifier.verify` (if provided).
6. If retry is enabled and issues exist (TODOs, logic mismatch, spec issues):
   1. Build `semantic_issues`.
   2. Call `Replanner.replan` and re-synthesize via `_synthesize_from_ir_tree`.
   3. Re-run SpecAuditor and compilation verification.
7. Return `code`, `dependencies`, `verification`, `resolved_dependencies`, `spec_issues`, and `trace`.

Outputs
1. `code`, `dependencies` (usings), and `trace` containing `ir_tree`, `best_path`, `blueprint`.

### 7. `src/ir_generator/ir_generator.py:IRGenerator.generate`
Inputs
1. StructuredSpec and optional `intent_hint`.

Flow
1. Normalize each raw step and extract hierarchical clauses.
2. Run step-local semantic analysis:
   1. Determine node type (`ACTION`, `CONDITION`, `LOOP`, `ELSE`, `END`, `WRAPPER`).
   2. Infer coarse `intent`, `role`, `cardinality`, and `target_entity`.
   3. Merge explicit semantic metadata from the design spec.
3. Resolve role-specific semantics:
   1. Infer `spec_role`.
   2. For `CHECK`, enrich `semantic_map` with `check_kind`, `check_subject`, `check_operator`, `check_value`, `expected_truth`, and `subject_resolution`.
   3. For `CALCULATE`, resolve canonical property and `entity_resolution`.
   4. For `FILTER`, apply promotion rules and retain `predicate_resolution` / `collection_resolution`.
4. Coerce final runtime `intent` / `role` and resolve final `source_kind`.
5. Determine `input_link` using structural dependency rules:
   1. First child in a structure uses structural parent dependency.
   2. Later siblings prefer sequential sibling dependency.
   3. `ELSE` branches use the parent `CONDITION` as branch base.
6. Emit IR nodes.
7. Insert explicit bridge nodes when required:
   1. `JSON_DESERIALIZE` after upstream string/file fetch.
   2. `JSON_SERIALIZE` before collection persist.
8. Attach nodes into the nested `logic_tree` and update context history.

Outputs
1. IR tree with `logic_tree`, `inputs`, `outputs`, and `data_sources`.

Implementation notes
1. The generator now delegates domain logic to:
   1. `src/ir_generator/check_resolution.py`
   2. `src/ir_generator/promotion_rules.py`
   3. `src/ir_generator/target_resolution.py`
   4. `src/ir_generator/spec_role_rules.py`
2. `ir_generator.py` remains the orchestration skeleton for clause handling, structure control, node emission, and auto-node insertion.

### 8. `src/code_synthesis/code_synthesizer.py:CodeSynthesizer._synthesize_from_ir_tree`
Inputs
1. IR tree plus `method_name`, `expected_steps`, optional type hints.

Flow
1. Create the initial synthesis path (`statements`, `all_usings`, `method_return_type`, etc.).
2. Emit candidate paths using `IREmitter.emit`.
3. Choose the best path and run `_audit_reachability`.
4. Build a blueprint via `BlueprintAssembler.create_blueprint`.
5. Call `CodeBuilderClient.build_code` to generate C#.

Outputs
1. `code` string, `dependencies`, and trace info.

### 9. `src/code_synthesis/ir_emitter.py:IREmitter.emit`
Inputs
1. `ir_tree`, `initial_candidates`, `beam_width`.

Flow
1. Walk IR nodes and generate candidate paths.
2. For each node, call `ActionSynthesizer.process_node`.
3. `ActionSynthesizer` maps specification-facing metadata into runtime execution choices:
   1. `spec_role=DESERIALIZE` -> `JSON_DESERIALIZE`
   2. `spec_role=FILTER` -> `LINQ`
   3. `spec_role=CHECK` keeps condition synthesis on the binder path
   4. `spec_role=CALCULATE` routes into calc handlers
4. `SemanticBinder` consumes `CHECK` metadata and provenance-strength to generate conservative conditions.
5. `calc_ops` consumes `entity_resolution` to decide whether to concretize, stay generic, or emit explicit TODO stop points.

Outputs
1. A ranked list of synthesis paths.

### 10. `src/utils/code_builder_client.py:CodeBuilderClient.build_code`
Inputs
1. `blueprint` dictionary.

Flow
1. Persist `blueprint` JSON to `cache/blueprints/<run_id>/blueprint.json`.
2. Run `dotnet run` for `tools/csharp/CodeBuilder`.
3. Parse the last output line as JSON.

Outputs
1. `{ code: "...", ... }` on success.
2. `{ status: "error", message: ... }` on failure.

### 11. `src/code_synthesis/code_synthesizer.py:CodeSynthesizer._audit_reachability`
Inputs
1. The best synthesis path.

Flow
1. Find source variables with roles `content`, `data`, `accumulator`.
2. Scan statements for sink usage (`PERSIST`, `DISPLAY`, `RETURN`, `NOTIFICATION`).
3. If any source is not consumed, append a warning comment statement.

Outputs
1. The path is mutated by appending a warning comment.

### 12. `src/code_verification/compilation_verifier.py:CompilationVerifier.verify`
Inputs
1. Source code, optional dependencies and work_dir.

Flow
1. Prepare a sandbox directory (reuse base sandbox if possible).
2. Create or update `Sandbox.csproj` with default and extra packages.
3. Normalize code (wrap in class if needed).
4. Run `dotnet build`.
5. Parse errors from build output.

Outputs
1. `{ valid: True }` on success.
2. `{ valid: False, errors: [...] }` on failure.

### 13. `src/replanner/replanner.py:Replanner.replan`
Inputs
1. `structured_spec`, `ir_tree`, `synthesis_result`, `verification_result`, `semantic_issues`.

Flow
1. Create hints from `ReasonAnalyzer.analyze`.
2. Add mismatch hints from `ReasonAnalyzer.analyze_logic_mismatch`.
3. Apply hints to IR using `IRPatcher.apply_patches`.
4. Return patched IR.

Outputs
1. `{ status: "REPLANNED", patched_ir: ... }` or failure status with message.

### 14. `src/replanner/reason_analyzer.py:ReasonAnalyzer.analyze`
Inputs
1. `synthesis_result`, `verification_result`, `semantic_issues`.

Flow
1. Convert compilation errors into patch hints by reading error code, line, and near-node comments.
2. Convert semantic issues (only TODOs in this flow) into patch hints.

Outputs
1. List of patch hints for `IRPatcher`.

## Key data objects
0. ProjectSpec
   1. `project_name`, `spec` (entities, DTOs, repositories, services, routes), and `method_specs`.
1. StructuredSpec
   1. `module_name`, `purpose`, `inputs`, `outputs`, `steps`, `constraints`, `test_cases`, `data_sources`.
2. IR tree
   1. `logic_tree` nodes with `intent`, `role`, `target_entity`, `semantic_map`, `source_kind`.
   2. `semantic_map` may include `spec_role`, `check_*`, `entity_resolution`, `subject_resolution`, `predicate_resolution`, `collection_resolution`.
3. Blueprint
   1. Method bodies and statements used by CodeBuilder.
4. VerificationResult
   1. `valid`, `errors`, `stdout`, `stderr`.
5. Replan hints
   1. `reason`, `detail`, `patch` with patch types.

## Consistency checks observed in this flow
1. StructuredSpec validation is performed twice.
   1. `StructuredDesignParser.parse_markdown` calls `validate_structured_spec_or_raise`.
   2. `synthesize_structured_spec` calls it again.
2. Data source resolution is enforced.
   1. `StructuredDesignParser._resolve_source_info` fills missing `source_kind`.
   2. `validate_structured_spec_or_raise` rejects unknown or invalid `source_ref` and `source_kind`.
3. IR-level intent and cardinality are normalized.
   1. `IRGenerator._analyze_step_integrated` adjusts intent based on logic goals and source kind.
4. Specification meaning is preserved independently from runtime role.
   1. `IRGenerator` emits `semantic_map.spec_role` and role-specific resolution metadata.
5. Structural dependency is normalized at IR time.
   1. First child / sibling / else-branch linkage is fixed before code synthesis.
6. Downstream conservatism is metadata-driven.
   1. Weak provenance stops over-concretization in `CHECK`, `FILTER`, and `CALCULATE`.
7. Reachability audit is applied on the final path.
   1. `_audit_reachability` adds a warning if source data never reaches sinks.
8. Safety policy and project rules are enforced for single-module generation.
   1. `enforce_safety_policy` blocks destructive/cautionary intents unless `--allow-unsafe`.
   2. `validate_design_path`, `validate_output_path`, `validate_spec_paths` enforce naming and banned patterns.
9. Spec alignment audit runs before final output.
   1. `SpecAuditor.audit` can block on `SPEC_INPUT_LINK_UNUSED`.
10. Compilation verification is enforced before final output.
   1. `CompilationVerifier.verify` runs `dotnet build` and returns structured errors.
11. Replan guards are present.
   1. Convergence guard prevents repeating hints more than once per hint fingerprint.
   2. Max retry count is capped in `generate_from_design.py`.

## Feature utilization and gaps
1. `NuGetClient` is used by `synthesize_structured_spec` to resolve packages from usings.
2. `resolve_nuget_deps` uses a fallback map for `Dapper`, `Newtonsoft.Json`, and `Microsoft.Extensions.Logging`.
3. `CompilationVerifier` still injects default packages, so some resolved deps can overlap.
4. Safety policy and project rules are enforced only in single-module mode, not in project generation.
5. Project audit reuses method-level synthesis; spec issues are surfaced but do not block generation unless the caller interprets them.

## SpecAuditor enhancements
1. **Intent coverage**
   1. IR node `intent` must be reflected in the generated statements for the same `node_id`.
   2. Special cases covered: `RETURN`, `TRANSFORM`, `CALC`, `LINQ`, `DISPLAY`, `LOOP`, `CONDITION`, and try/catch wrappers.
2. **input_refs usage**
   1. `input_refs` declared in the spec must be consumed in the target step’s statement texts.
   2. Self-references (ref == step_id) are ignored to avoid false positives.
3. **input_link usage**
   1. Loop inner nodes (`*_inner`) are validated against the parent loop’s statements.
   2. If the parent loop consumes the upstream output, the inner node is treated as aligned.

## Prohibited rules check (safety and project rules)
1. Safety policy is enforced for single-module generation unless `--allow-unsafe`.
2. Project rules are enforced for single-module generation and for project design path validation.
3. Project generation does not currently validate module names inside the ProjectSpec against naming conventions or banned patterns.

## Notes
1. `CompilationVerifier` leaves temporary work directories on disk by default.
2. `CodeBuilderClient` trusts the last line of stdout as JSON; non-JSON output triggers a failure.
3. Deterministic completion assumes stable assets (vector models, dictionaries, method store); changes in those assets may change outcomes but remain traceable by path/version.
