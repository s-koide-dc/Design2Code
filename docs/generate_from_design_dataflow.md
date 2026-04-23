# generate_from_design dataflow (method-level)

## Scope
This document covers the data flow triggered by `scripts/generate/generate_from_design.py` and the concrete methods it calls directly or indirectly during the design-to-code pipeline.

## High-level flow summary
### Single-module mode (default)
1. Read a `.design.md` file and parse it into a StructuredSpec.
2. Validate the StructuredSpec.
3. Enforce safety policy and project rules.
4. Convert the StructuredSpec into an IR tree.
5. Synthesize C# code via blueprint emission and CodeBuilder.
6. Run SpecAuditor and optional replanning retries.
7. Verify compilation in a sandbox.
8. Optionally run execution verification.
9. Write the final `.cs` output file.

### Project mode (`--project`)
1. Read a project `.design.md` file and parse it into a ProjectSpec.
2. Enforce project rules.
3. Generate the multi-file project via `ProjectGenerator`.
4. Optionally audit method specs via SpecAuditor/Replanner.
5. Optionally run C# analysis or refactoring analysis.
6. Verify compilation of the generated project.

## Infer-Then-Freeze Policy (Design Spec Inference)
This flow applies when a design spec omits explicit metadata and the system performs deterministic inference once, then persists the inferred metadata into the `.design.md` before generation.

1. Parse the raw `.design.md` into a preliminary StructuredSpec.
2. Detect missing explicit metadata in Core Logic (`ops`, `semantic_roles`, `data_source`, `refs`).
3. Run deterministic inference using fixed assets and scoring rules to propose metadata.
4. Persist the inferred metadata back into the `.design.md` (this becomes the single source of truth).
5. Re-parse the updated `.design.md` and continue the standard generation flow.
6. Record the asset versions used for inference in logs or design metadata to ensure traceability.

## Implementation Placement (Recommended)
1. `scripts/generate/generate_from_design.py:main`
   - After reading the `.design.md` but before strict validation, run inference if missing metadata is detected.
   - Write back inferred tags and the `### Inference Metadata` block.
   - Re-parse and then run `validate_structured_spec_or_raise`.
2. `src/design_parser/structured_parser.py`
   - Remains deterministic and metadata-driven; it does not perform inference.
3. `src/utils/design_doc_refiner.py`
   - Preferred location for deterministic inference rules and write-back utilities.
4. `src/utils/design_sync_util.py`
   - Optional helper for targeted step updates (used only if required by refiner).

## Inference Rules (Deterministic)
1. Inference is only allowed when explicit metadata is missing.
2. Inference must never overwrite explicit `[KIND|...]`, `[ops:...]`, `[semantic_roles:{...}]`, `[data_source|...]`, or `[refs:...]`.
3. Inference must use fixed assets and fixed scoring rules. No randomness is permitted.
4. If confidence is below the configured threshold, inference must not insert metadata and must instead emit a blocking issue.
5. The output of inference must be stable for identical inputs under identical asset versions.

## Inference Scope (What Can Be Filled)
Inference is limited to the following missing elements:
1. Step metadata: `KIND`, `INTENT`, `TARGET`, `OUTPUT`, `SIDE_EFFECT`.
2. `refs` (input dependencies) when a step is missing explicit refs.
3. `data_source` declarations for steps that clearly reference a known store or path.
4. `semantic_roles` for:
   - `DATABASE_QUERY` / `PERSIST` → `semantic_roles.sql` (only if SQL is explicitly present in text).
   - `HTTP_REQUEST` → `semantic_roles.url` (only if URL is explicitly present in text).
   - `CMD_RUN` → `semantic_roles.command` (only if command text is explicitly present in text).
5. `source_kind` when `source_ref` is inferred and a valid data source is present.

## Inference Order (Deterministic)
1. Identify explicit tags and lock them.
2. Infer `data_source` candidates and `source_kind`.
3. Infer step `KIND/INTENT/TARGET/OUTPUT/SIDE_EFFECT`.
4. Infer `refs` based on nearest previous step with compatible output.
5. Infer `semantic_roles` from explicit literals in the line (URL/SQL/command).
6. Recompute a normalized line with the inferred tags and persist to `.design.md`.

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
```
Notes:
1. Do not include timestamps in the design doc to preserve deterministic output.
2. The fingerprint must be reproducible from normalized inputs and asset versions.

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
2. Optional mode flags: `--project`, `--project-audit-only`, `--no-project-audit`, `--allow-unsafe`, `--strict-semantics`, `--allow-fallback`, `--post-exec-verify`, `--post-csharp-analyze`, `--post-refactor-analyze`.

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
   1. Parse and validate the design:
      1. `StructuredDesignParser.parse_design_file`.
      2. `validate_structured_spec_or_raise`.
   2. Enforce safety policy unless `--allow-unsafe`.
   3. Enforce project rules (design path, output path, banned patterns).
   4. Synthesize code using `synthesize_structured_spec` (SpecAuditor + optional replanning).
   5. Optionally run execution verification (`ExecutionVerifier`) when `--post-exec-verify` is set.
   6. Write the final code to `output_path`.

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
1. Convert each step into IR nodes:
   1. Determine node type (ACTION, CONDITION, LOOP, ELSE, END).
   2. Infer intent and role using `SynthesisIntentDetector` and logic analysis.
   3. Carry `source_ref` and infer `source_kind` from declarations or semantics.
   4. Create `semantic_map` including logic goals and semantic roles.
2. Insert auto-chaining nodes for JSON deserialize or serialize when conditions match.
3. Build a nested `logic_tree` with `children` and `else_children`.

Outputs
1. IR tree with `logic_tree`, `inputs`, `outputs`, and `data_sources`.

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
4. Reachability audit is applied on the final path.
   1. `_audit_reachability` adds a warning if source data never reaches sinks.
5. Safety policy and project rules are enforced for single-module generation.
   1. `enforce_safety_policy` blocks destructive/cautionary intents unless `--allow-unsafe`.
   2. `validate_design_path`, `validate_output_path`, `validate_spec_paths` enforce naming and banned patterns.
6. Spec alignment audit runs before final output.
   1. `SpecAuditor.audit` can block on `SPEC_INPUT_LINK_UNUSED`.
7. Compilation verification is enforced before final output.
   1. `CompilationVerifier.verify` runs `dotnet build` and returns structured errors.
8. Replan guards are present.
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
