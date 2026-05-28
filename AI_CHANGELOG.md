# AI Changelog

- **2026-05-28**: Fixed the default-smoke regression to assert that `test_vector_cache_required` is excluded from CI-oriented default runs, and documented in `scripts/README.md` that GitHub Actions executes only asset-free smoke profiles because chiVe, caches, and `dictionary.db` are not committed.

- **2026-05-28**: Split `test_vector_cache_required` out of the default `run_unit_smoke.py` targets into a dedicated `assets` profile and changed the GitHub Actions workflow to run only `core`, `parser`, and `synthesis`, so CI no longer depends on local vector-cache assets that are absent on GitHub-hosted runners.

- **2026-05-28**: Updated `.github/workflows/python-ci.yml` from `actions/checkout@v4` / `actions/setup-python@v5` to `@v6`, aligning the CI workflow with GitHub's Node 24-compatible action releases and removing the runner deprecation warning path reported after commit.

- **2026-05-28**: Expanded the `run_unit_smoke.py` profile documentation in `scripts/README.md` to list the exact test modules behind `core`, `parser`, and `synthesis`, and added a short source comment explaining why the smoke profile set stays explicit.

- **2026-05-28**: Documented `python scripts/validate/run_unit_smoke.py --profile core --verbosity 2` in `scripts/README.md` as the shortest local smoke path, reflecting the new profile split with a concrete operator-facing command.

- **2026-05-28**: Added `core` / `parser` / `synthesis` profile selection to `scripts/validate/run_unit_smoke.py` while preserving the expanded default suite, documented the profile behavior, and fixed the `parser` profile success path with an integration regression.

- **2026-05-28**: Broadened the default `scripts/validate/run_unit_smoke.py` suite with lightweight configuration/design/dependency guards (`test_config_manager`, `test_design_doc_parser`, `test_dependency_resolver`, `test_json_deserialize_guard`), documented the expanded default set, and added an integration regression that fixes the default-smoke stdout success path.

- **2026-05-28**: Expanded `.github/workflows/python-ci.yml` to run `scripts/validate/run_unit_smoke.py --verbosity 2`, so the existing public-entrypoint/security/consistency checks are now complemented by the default unit smoke suite in CI; updated the staged improvement memo accordingly.

- **2026-05-28**: Tightened the README's `現在の温度感` section to reflect the now-stable docs-validation boundary, explicitly listing `scripts/validate_project_consistency.py` as a stable entrypoint and noting the mode-based doc policy plus grouped validator reporting.

- **2026-05-28**: Added a short operational checklist to `config/README.md` for `doc_reference_policy.json` changes, documenting the required validator run, integration regression run, and follow-up README/doc mode synchronization.

- **2026-05-28**: Extended `config/README.md` so `doc_reference_policy.json` now documents the exact `validate_project_consistency.py` stderr section mapping from policy keys to `DOCS (...)` and `GENERAL`.

- **2026-05-28**: Documented the new grouped docs-validator stderr layout in `README.md` and `scripts/README.md`, so operators can see that `validate_project_consistency.py` now separates `GENERAL` errors from the three document-mode sections.

- **2026-05-28**: Grouped `scripts/validate_project_consistency.py` stderr output by `GENERAL`, `DOCS (required)`, `DOCS (existence-only)`, and `DOCS (optional-reference)` sections while preserving the per-line diagnostics, and synchronized the integration assertions for the new scan order.

- **2026-05-28**: Updated `scripts/validate_project_consistency.py` to include doc-validation mode labels in stderr diagnostics, so missing or broken docs now explicitly report whether they failed under `required`, `existence-only`, or `optional-reference` handling; synchronized the corresponding integration assertions.

- **2026-05-28**: Added matching document-contract notes to `docs/generate_from_design_dataflow.md` and `docs/method_store_spec.md`, aligning the whole `required_docs` set around a consistent statement of what each document owns relative to the README.

- **2026-05-28**: Added a short document-contract note to `docs/project_overview.md`, clarifying that it is a `required_docs` overview tied to the README's public entrypoints while serving as the broader internal structure map.

- **2026-05-28**: Annotated the README's main document list with doc-validation modes, so readers can immediately distinguish `required_docs` from `existence_only_docs` without cross-checking the policy file.

- **2026-05-28**: Added direct links from the README entrypoint section to `config/README.md` and `resources/README.md`, so readers can move from each public entrypoint to its configuration dependencies and representative generated assets without searching the repository.

- **2026-05-28**: Extended `config/README.md` with an entrypoint-to-config map, so the documented public and maintenance scripts now show which JSON settings they primarily depend on without requiring readers to inspect `ConfigManager` or each CLI source file.

- **2026-05-28**: Extended `resources/README.md` with a setup-to-artifact map, so the bootstrap commands in `README.md` now trace directly to the representative files they create or refresh under `resources/`.

- **2026-05-28**: Reworked `resources/README.md` into an explicit inventory document by separating stable reference assets from generated examples and aligning the vector filenames with the current `mc90` artifacts, so its `existence_only_docs` role is clearer and less misleading.

- **2026-05-28**: Documented the doc-validation mode policy in `README.md` and `scripts/README.md`, so operators can tell when a document belongs in `required_docs`, `existence_only_docs`, or `optional_reference_docs` without reading only the raw policy JSON.

- **2026-05-28**: Generalized doc validation modes again by introducing `optional_reference_docs` in `config/doc_reference_policy.json`; temporary planning docs can now be absent without failing validation, but if present their local references are still checked. Added regression coverage for broken links inside the staged-improvement plan doc.

- **2026-05-28**: Added doc-validation modes to `config/doc_reference_policy.json` by introducing `existence_only_docs`, and placed `resources/README.md` under that mode so inventory-style docs are checked for presence without validating every listed generated asset; added regression coverage for both missing existence-only docs and ignored inventory entries.

- **2026-05-28**: Expanded `config/doc_reference_policy.json` again so `config/README.md` is now enforced as a required public document, while explicitly leaving generated-asset inventory docs such as `resources/README.md` out of the required set for now; added regression coverage for a missing required config README.

- **2026-05-28**: Expanded `config/doc_reference_policy.json` so `docs/project_overview.md`, `docs/generate_from_design_dataflow.md`, and `docs/method_store_spec.md` are now treated as required public docs alongside the README pair and stdout policy; added regression coverage for a missing required overview document.

- **2026-05-28**: Added regression coverage for malformed `config/doc_reference_policy.json`, so `scripts/validate_project_consistency.py` now has a fixed stderr failure path when `required_docs` or `temporary_docs` stop being string arrays.

- **2026-05-28**: Externalized the public-doc monitoring target list into `config/doc_reference_policy.json`, so `scripts/validate_project_consistency.py` now reads its required-doc set from configuration instead of hardcoding it; added regression coverage for both the default temporary-doc behavior and a config override that promotes the plan memo to a required doc.

- **2026-05-28**: Relaxed the new doc-reference validation so `docs/README実装ギャップ段階改善計画.md` is treated as a temporary working note rather than a required public document; `validate_project_consistency.py` now enforces only durable public docs, and regression coverage confirms the temporary plan doc can be absent without failing validation.

- **2026-05-28**: Extended `scripts/validate_project_consistency.py` to validate local references in `README.md`, `scripts/README.md`, and `docs/stdout_output_policy.md`, so broken public-document links now fail the consistency check with stderr diagnostics; added regression coverage for a broken README reference.

- **2026-05-22**: Hardened `scripts/validate_project_consistency.py` for missing or invalid `ai_project_map.json` by initializing its empty-state sets before validation, and added regression coverage for the stderr error path instead of letting the script crash with `UnboundLocalError`.

- **2026-05-22**: Extended the Phase 3 CLI contract to `scripts/sync_project_map.py` and `scripts/validate_project_consistency.py`, separating progress/success to stdout from warnings and errors on stderr, and added regression coverage for missing map files plus the clean success path.

- **2026-05-22**: Extended the Phase 3 CLI contract to `scripts/data/build_knowledge_base.py`, separating maintenance progress to stdout from missing-dictionary warnings and persistence failures on stderr, and added regression coverage for the warning-while-continuing path.

- **2026-05-22**: Extended the Phase 3 CLI contract to the network bootstrap scripts `scripts/data/fetch_jmdict.py` and `scripts/data/fetch_vectors.py`, adding stdout progress, Japanese stderr diagnostics, environment-based URL overrides for deterministic failure testing, and regression coverage for download failures.

- **2026-05-22**: Extended the Phase 3 CLI output contract to `scripts/data/convert_vectors.py` and `scripts/data/parse_jmdict.py`, routing progress to stdout and missing-input failures to Japanese stderr diagnostics, and added regression coverage for those failure paths.

- **2026-05-22**: Localized the main `scripts/generate/generate_from_design.py` stderr diagnostics into Japanese for public-facing failure paths such as missing design docs, policy violations, synthesis failures, and spec-alignment stops, while keeping the stdout/stderr contract added earlier.

- **2026-05-22**: Continued Phase 3 CLI output unification by routing `scripts/generate/generate_from_design.py` progress/success messages to stdout while moving error and warning paths to stderr, and added regression coverage for missing design documents plus policy documentation for the split.

- **2026-05-22**: Started Phase 3 CLI output unification by adding `src/utils/cli_output.py`, updating `scripts/validate/run_tdd.py` so successful runs emit formal JSON on stdout while argument/input failures emit Japanese diagnostics on stderr, and adding regression coverage plus policy documentation for that contract.

- **2026-05-22**: Updated `README.md` to publish two verified conversational entrypoint examples through `Pipeline(is_test_mode=True)`: one for `GET_CWD` and one for `LIST_DIR`, keeping the README aligned with the tested natural-language paths.

- **2026-05-22**: Continued Phase 2 by expanding the real `LIST_DIR` intent corpus with natural folder-listing phrasings and adding integration coverage in `tests/integration/test_documented_entrypoints.py`, so directory-list requests no longer depend on explicitly saying only `一覧`.

- **2026-05-22**: Continued Phase 2 README/implementation alignment by expanding the real `GET_CWD` intent corpus with natural directory-query variants and adding integration coverage in `tests/integration/test_documented_entrypoints.py` so multiple README-safe phrasings stay executable through the pipeline.

- **2026-05-21**: Started staged README/implementation alignment by rewriting `README.md` to reflect verified behavior instead of aspirational claims, adding `docs/README実装ギャップ段階改善計画.md` to sequence the remaining work, and introducing `tests/integration/test_documented_entrypoints.py` to keep the documented public entrypoints executable.

- **2026-05-21**: Fixed C# integration tests in `tests/unit/test_code_synthesizer_integration.py` by instantiating `CodeBuilderClient` with a mock config pointing to `os.getcwd()`, preventing test workspace isolation from hiding C# compilation assets.

- **2026-05-15**: Added `research/ir_meaning_preservation/report.md` as the formal integrated report that connects the research objective, benchmark method, core findings, runtime/schema/policy boundary, implementation sites, operationalization, remaining open issues, and final conclusion into a single document, and synchronized the research indexes accordingly.

- **2026-05-15**: Added `research/ir_meaning_preservation/runtime_schema_policy_boundary.md` to compress the final `runtime / schema / policy` responsibility split into a single statement, and synchronized the research README, document map, outcome memo, and goal-state summary so the closure phase now has an explicit boundary document.

- **2026-05-13**: Added deterministic source provenance for `spec_role=CALCULATE` by introducing `src/ir_generator/calculate_resolution.py`, preserving explicit `source_var` or structural `input_link` as `calculate_source_resolution` / `calculate_source_node_id`, teaching `calc_ops` to prefer exact upstream vars over `active_scope_item` and latest-var fallback, and synchronizing the affected design/research/regression artifacts.

- **2026-05-13**: Extended `ITERATE` continuity from item entity to explicit item alias by preserving `iteration_item_var` / `iteration_item_var_resolution`, propagating that alias through loop codegen so nested branch children keep the same `foreach` item name instead of falling back to generic `item`, and synchronizing the affected design/research/regression artifacts.

- **2026-05-13**: Materialized deterministic default retry-policy provenance for `spec_role=WRAP` by extending `wrapper_resolution` to emit `default_attempts` / `default_exception_type` / `default_no_delay_policy`, preserving those resolution fields through `IREmitter` into `retry` statements, adding direct IR/code-synthesis regressions for default-policy wrappers, and synchronizing the wrapper design/research/regression artifacts.

- **2026-05-11**: Added deterministic literal-return handling by introducing `src/ir_generator/return_resolution.py`, preserving `return_value` / `return_value_resolution` for `true` / `false` / `null` / numeric / quoted-literal returns, teaching `ActionSynthesizer` to prioritize that metadata over latest-variable fallback, adding direct IR/code-synthesis regressions for literal returns, and synchronizing the affected design/research artifacts.

- **2026-05-12**: Extended `RETURN` stabilization from literal-only metadata to exact upstream source preservation by normalizing explicit `source_var`, attaching `return_source_node_id` for non-literal chained returns, prioritizing input-link-derived exact var resolution over latest-typed-var fallback in `ActionSynthesizer`, and updating the role-weakening baseline to cover chained return integrity.

- **2026-05-12**: Added `case_32_return_provenance_contrast` plus `return_provenance_observation.md` to close the research loop for `RETURN` provenance, fixing branch-local return-source metadata so `input_link_var` points at the semantic upstream source rather than the structural `CONDITION` base.

- **2026-05-12**: Added `return_provenance_supply_model.md` plus `case_33` / `case_34` and `return_provenance_supply_observation.md` to fix the supply boundary for `RETURN` provenance, distinguishing deterministic `input_link_var` supply from provenance-free weak retention when no literal or structural source is available.

- **2026-05-11**: Elevated `spec_role=WRAP` from marker-comment preservation to deterministic retry semantics by emitting structured `retry` statements in `IREmitter`, teaching both the Python fallback renderer and C# `CodeBuilder` to render them as `for + try/catch + break/rethrow`, adding direct integration assertions for wrapper code generation, and documenting the new wrapper-semantics boundary in code-synthesis and research artifacts.

- **2026-05-11**: Added deterministic wrapper-metadata resolution for retry semantics by introducing `src/ir_generator/wrapper_resolution.py`, preserving explicit `max_attempts` / `exception_type`, inferring retry count only from tokenized `<number> + 回` sequences, and extending IR/code-synthesis regressions to verify explicit retry metadata reaches generated C#.

- **2026-05-11**: Extended retry-wrapper semantics with explicit delay/backoff policy propagation by preserving `base_delay_ms`, `max_delay_ms`, and `backoff_multiplier` metadata from IR through `IREmitter` into both the Python fallback renderer and C# `CodeBuilder`, with sync `Thread.Sleep` / async `Task.Delay` generation and matching regression coverage.

- **2026-05-11**: Fixed `CodeBuilderClient` executable selection to choose the newest available Debug/Release binary instead of always preferring Release, preventing stale CodeBuilder builds from masking current retry-semantics changes in runtime validation.

- **2026-05-11**: Strengthened runtime-side handling for weak structural/transform roles by (1) bridging `spec_role=TRANSFORM` with weak `GENERAL/ACTION` intent to the transform handler in `ActionSynthesizer`, and (2) adding a conservative `spec_role=WRAP` consumer in `IREmitter` that preserves wrapper child bodies with a `wrapper:retry` marker instead of collapsing to a generic fallback action; added direct integration regressions for `TRANSFORM`, `ITERATE`, and `WRAP`, and synchronized the affected design/research documents.

- **2026-05-08**: Added `--update-run-file` support to `run_ir_meaning_preservation_regression.py` so the runner can reconstruct and rewrite a regression run record in place from the current draft generators, and documented the in-place update flow in the combined playbook, templates README, results README, and scripts catalog.

- **2026-05-08**: Added `--write-draft` and optional `--draft-file` support to `run_ir_meaning_preservation_regression.py`, verified default draft emission into `research/ir_meaning_preservation/results/regression_run_2026_05_07_metadata_baseline.runner_draft.md`, and documented the default/output override behavior in the playbook, templates README, scripts catalog, and results README.

- **2026-05-08**: Extended `run_ir_meaning_preservation_regression.py` one final step to emit a paste-ready `Final Judgment` draft sourced from the current run file, and updated the playbook/template documentation to state that the runner can now regenerate the full operational body of a regression record as draft text.

- **2026-05-08**: Completed the regression-record drafting support in `run_ir_meaning_preservation_regression.py` by adding a paste-ready `Final Judgment` candidate block sourced from the current run file's regression status, open risks, and next action, so the runner now proposes draft content for the full operational body of a regression record.

- **2026-05-07**: Completed the regression-run draft generator by extending `run_ir_meaning_preservation_regression.py` to emit paste-ready `Output Path Check` and `Deliverables Produced` blocks, so the runner now covers the full operational body of a regression record aside from final judgment editing.

- **2026-05-07**: Extended `run_ir_meaning_preservation_regression.py` to emit paste-ready draft blocks for `Affected Claims` and `Downstream Conservatism Check`, reusing the current run file's claim text, claim-map references, consumer list, and stronger/weaker fallback notes so a follow-up regression record can be drafted with minimal manual copying.

- **2026-05-07**: Extended `run_ir_meaning_preservation_regression.py` so the runner now emits a paste-ready `Change Summary` / `Benchmark Coverage` draft block by reusing the current run file's changed-area, related-file, and benchmark-coverage entries, reducing manual rewriting when preparing the next regression record.

- **2026-05-07**: Extended `run_ir_meaning_preservation_regression.py` again so the runner now emits a paste-ready draft block for `Role Weakening Check` and `Alias Admission Check`, seeded from the run file's affected roles and alias timing root plus the corresponding regression-table checks.

- **2026-05-07**: Added a shared `scripts/validate/ir_meaning_preservation_regression_lib.py` helper and extended `run_ir_meaning_preservation_regression.py` so the runner now reprints the exact `Regression Check` rows implied by the run file's `Affected spec_role` values and alias timing root/admission state, both in the console summary and in the paste-ready markdown block.

- **2026-05-07**: Improved `run_ir_meaning_preservation_regression.py` so the runner now captures each step's output and emits a paste-ready markdown block for the `Validation Run` section of a regression record, with concise logical commands (`python ...`) and summarized outcomes instead of raw interpreter paths.

- **2026-05-07**: Extended `validate_ir_meaning_preservation_regression.py` to verify that `Affected spec_role` values exist in `results/role_weakening_regression_table.md` and that the run-record alias timing root / admission state resolves to a valid row in `results/schema_alias_admission_regression_table.md`, with explicit normalization from operational states (`Admit Now`, `Hold For Evidence`, `Reject`) to table states (`admitted`, `not admitted`); updated the playbook and regression template accordingly.

- **2026-05-07**: Added `scripts/validate/run_ir_meaning_preservation_regression.py` to execute the standard IR meaning-preservation playbook as a single command by chaining project-map sync, project consistency validation, regression-run validation, and an optional predefined IR test suite; wired it into the safety whitelist, scripts catalog, regression template, playbook, checklist, and results/template indexes, and verified it against the metadata-baseline run with the `ir-core` suite.

- **2026-05-07**: Added `scripts/validate/validate_ir_meaning_preservation_regression.py` to semi-automate IR meaning-preservation regression runs by validating the run-record structure, required policy/result assets, output-path review section, and referenced files; updated the regression template, baseline run record, playbook, checklist, scripts catalog, safety whitelist, and results/template READMEs to use the new validator.

- **2026-05-07**: Integrated `docs/stdout_output_policy.md` into the research-operation layer by extending the regression run template, benchmark addition template, regression checklist, combined playbook, and templates README with explicit output-path verification steps.

- **2026-05-07**: Backfilled missing output-path guidance in source-level design documents for `ActionSynthesizer`, `IRGenerator`, `DesignDocRefiner`, `Replanner`, and `ServiceGeneration`, aligning them with `docs/stdout_output_policy.md` so the `stdout / stderr / debug_print / logger` boundary is documented consistently.

- **2026-05-07**: Added `docs/stdout_output_policy.md` to normalize the project's output channels into `Formal CLI stdout`, `Formal CLI stderr`, `debug_print`, and `logger`, and linked it from `docs/project_overview.md` as the canonical guide for future output-path changes.

- **2026-05-07**: Continued internal diagnostic cleanup by moving `ResponseGenerator`, `TDDOperations`, `DesignSyncUtil`, and `SandboxProvisioner` away from unconditional `print` usage toward logger-based reporting, and synchronized their source-level design documents with the no-stdout internal-output policy.

- **2026-05-07**: Continued internal diagnostic cleanup by routing `ProjectGenerator` missing-module notices and `ExecutionVerifier` mock-file notices through `debug_print`, and moving `TemplateRegistry` / `UnifiedKnowledgeBase` load failures to logger-based reporting; synchronized the related source-level design documents and fixed the affected generator helper indentation.

- **2026-05-07**: Continued internal-output cleanup by routing `AutonomousAligner` manual summary output and `StructuralMemory.find_duplicates` candidate tracing through `src.utils.stdout_guard.debug_print`, and synchronized their source-level design documents with the opt-in debug-output policy.

- **2026-05-07**: Defined the stdout/stderr contract for `Pipeline` REPL and `QualityGateChecker` CLI by isolating user-facing stdout emission from diagnostic stderr emission in code, and updated the corresponding source-level design documents to make the output boundary explicit.

- **2026-05-07**: Continued stdout cleanup on internal diagnostic paths by moving `IntentDetector`, `VectorEngine`, `KnowledgeExtractor`, `LogManager`, and `TaskManager` away from unconditional `print` usage toward logger output or `debug_print` fallbacks, and synchronized the corresponding source-level design documents with the revised output policy.

- **2026-05-07**: Extended stdout cleanup across manual verification and internal progress paths by routing `AdvancedTDDSupport`, `ClarificationManager`, `SyntacticAnalyzer`, and `AutonomousSynthesizer` sample/progress output through `src.utils.stdout_guard.debug_print`, and synchronized their source-level design documents with the opt-in debug-output policy.

- **2026-05-07**: Continued stdout cleanup by routing `__main__` demo/sample output in `MorphAnalyzer`, `DesignDocParser`, and `NuGetClient` through `src.utils.stdout_guard.debug_print`, keeping manual inspection paths available behind `NLP_DEBUG_STDOUT` while leaving CLI-facing output untouched; also re-inventoried remaining `print` sites to separate user-facing paths from future cleanup targets.

- **2026-05-07**: Continued stdout cleanup across the design-to-code pipeline by moving internal diagnostic output in `CodeBuilderClient`, `Replanner`, `DesignDocRefiner`, `ServiceGenerationHelper`, and `ProjectGenerator` away from unconditional `print` usage toward logger/debug-gated paths, and synchronized the affected source-level design documents with the new output policy.

- **2026-05-07**: Moved the `DI Generated Code` dump in `tests/unit/test_code_synthesizer_integration.py` behind the opt-in `NLP_TEST_DEBUG_STDOUT` flag so normal test runs stay quiet while keeping a targeted diagnostic path available.

- **2026-05-07**: Cleaned up always-on debug output in `IRGenerator` and `ActionSynthesizer` by routing diagnostic prints through `src/utils/stdout_guard.py` as opt-in `NLP_DEBUG_STDOUT` logging, and updated the corresponding source-level design documents to reflect the new stdout policy.

- **2026-05-07**: Added `research/ir_meaning_preservation/combined_regression_playbook.md` to combine role-weakening and schema-alias-admission regression into one repeatable operating procedure, and linked it from the research summary indexes.

- **2026-05-07**: Added `research/ir_meaning_preservation/results/schema_alias_admission_regression_table.md` to normalize alias-admission regression checks by timing root, admission state, IR effect, downstream impact, and required verification points, and linked it from the research indexes.

- **2026-05-07**: Added `research/ir_meaning_preservation/results/role_weakening_regression_table.md` to normalize role-weakening regression checks by `spec_role`, runtime bridge point, baseline status, evidence, and required verification points, and linked it from the research indexes.

- **2026-05-07**: Added `research/ir_meaning_preservation/results/regression_run_2026_05_07_metadata_baseline.md` as the first concrete regression-run record based on the new templates, fixing the current metadata-driven IR/synthesis behavior as an operational baseline after running the focused IR/code-synthesis test suite and project consistency validation.

- **2026-05-07**: Added reusable research operation templates under `research/templates/` for IR meaning-preservation regression runs and benchmark additions, and linked them from the research README, document map, and schema-alias/role-weakening checklist so the current claims can be carried into repeatable validation workflows.

- **2026-05-07**: Added missing source-level design documents for `design_parser.data_source_utils`, `design_parser.design_inference`, `ir_generator.check_resolution`, `ir_generator.promotion_rules`, `ir_generator.spec_role_rules`, `ir_generator.target_resolution`, `utils.entity_inference`, and `utils.stdout_guard`, and refreshed the module-level design documents for `ir_generator`, `action_synthesizer`, `semantic_binder`, and `calc_ops` to match the current metadata-driven IR and synthesis flow.

- **2026-05-01**: Updated the module design documents to match the current IR meaning-preservation implementation: rewrote `docs/ir_design.md`, expanded `docs/generate_from_design_dataflow.md` with role-specific resolution and metadata-driven synthesis flow, added `docs/ir_generator_module_design.md`, and refreshed `docs/project_overview.md` with the decomposed `ir_generator` and code-synthesis metadata consumer map.

- **2026-05-01**: Added `research/ir_meaning_preservation/executive_summary.md` as a short external-facing summary that compresses the current research into its problem statement, main findings, demonstrated outcomes, and final framing.

- **2026-05-01**: Added `research/ir_meaning_preservation/goal_state.md` to define the research endpoint, done conditions, and the boundary between expansion work and closure work.

- **2026-05-01**: Added `research/ir_meaning_preservation/schema_alias_role_weakening_regression_checklist.md` to convert the current role-weakening and alias-admission claims into a concrete regression workflow for future schema and IR changes.

- **2026-05-01**: Added `research/ir_meaning_preservation/implementation_priority_from_claims.md` to derive the next implementation priorities from the `substantiated` vs `implemented` split in the claim/evidence/implementation map.

- **2026-05-01**: Added `research/ir_meaning_preservation/claim_evidence_implementation_map.md` to connect each research claim to its benchmark evidence and implementation sites, making the research-to-code trace explicit.

- **2026-05-01**: Added `research/ir_meaning_preservation/research_outcome_memo.md` to compress the current research into a one-page memo organized by the three layers `role`, `provenance`, and `alias admission timing`.

- **2026-05-01**: Added `research/ir_meaning_preservation/results/schema_alias_admission_status_table.md` to normalize current alias-admission status across the five timing roots, making schema admission state and IR-side canonicalization readable without opening each case file.

- **2026-05-01**: Added `research/ir_meaning_preservation/schema_alias_admission_timing_matrix.md` to normalize the five alias-admission timing roots into a single cross-case table, and integrated that layer into the midterm synthesis beside role and provenance.

- **2026-05-01**: Captured observed IR for `case_31_external_compatibility_threshold`, extending `research/ir_meaning_preservation/results/schema_alias_admission_threshold_observation.md` so schema-admission timing is now grounded in five roots: `Hold For Evidence`, `Repeated Spec Use`, `Cross-Case Relevance`, `Downstream Impact`, and `External Compatibility`.

- **2026-05-01**: Captured observed IR for `case_29_cross_case_relevance_threshold` and `case_30_downstream_impact_threshold`, extending `research/ir_meaning_preservation/results/schema_alias_admission_threshold_observation.md` so admission timing is now grounded in `Hold For Evidence`, `Repeated Spec Use`, `Cross-Case Relevance`, and `Downstream Impact`.

- **2026-05-01**: Captured observed IR for `case_27_admissible_but_deferred_alias` and `case_28_repeated_spec_use_promotes_alias`, and added `research/ir_meaning_preservation/results/schema_alias_admission_threshold_observation.md` to show that admission threshold is best modeled as schema-admission timing rather than runtime inference.

- **2026-05-01**: Added `research/ir_meaning_preservation/schema_alias_admission_threshold.md` to define when owner-confined but low-evidence aliases should be admitted now, held for evidence, or rejected, separating `can_admit` from `should_admit_now`.

- **2026-05-01**: Captured observed IR for `case_26_legacy_field_bridge_admission` and extended `research/ir_meaning_preservation/results/schema_alias_tier2_observation.md` to show that `legacy field bridge` and `compound-part shorthand` share the same Tier 2 admission conditions when owner explanation and canonical non-ambiguity are satisfied.

- **2026-05-01**: Captured observed IR for `case_24_conditional_alias_with_owner_explanation` and `case_25_generic_abbreviation_rejection`, and added `research/ir_meaning_preservation/results/schema_alias_tier2_observation.md` to show that `Tier 2` alias admission depends on owner explanation and canonical non-ambiguity rather than abbreviation surface alone.

- **2026-05-01**: Captured observed IR for `case_22_allowed_alias_admission` and `case_23_disallowed_generic_alias_rejection`, and added `research/ir_meaning_preservation/results/schema_alias_coverage_observation.md` to show that policy-approved alias admission and intentionally rejected generic alias retention are now cleanly distinguishable.

- **2026-05-01**: Added alias-coverage policy contrast benchmarks `case_22_allowed_alias_admission.md` and `case_23_disallowed_generic_alias_rejection.md` to distinguish policy-approved alias admission from intentionally rejected generic alias retention.

- **2026-05-01**: Added `research/ir_meaning_preservation/schema_alias_coverage_policy.md` to define alias admission/rejection rules, coverage tiers, and the benchmark-facing boundary between allowable alias gaps and intentionally disallowed generic aliases.

- **2026-05-01**: Captured observed IR for `case_20_schema_alias_supplied_canonicalization` and `case_21_schema_alias_missing_weak_retention`, and added `research/ir_meaning_preservation/results/schema_alias_supply_observation.md` to show that alias supply success and weak-retention contrast are now cleanly distinguishable.

- **2026-05-01**: Added alias-supply contrast benchmarks `case_20_schema_alias_supplied_canonicalization.md` and `case_21_schema_alias_missing_weak_retention.md` to separate `supply failure` from `promotion failure` in property-side provenance evaluation.

- **2026-05-01**: Added `research/ir_meaning_preservation/schema_alias_supply_model.md` to define how property aliases must be supplied deterministically through `entity_schema`, including exact-match-only canonicalization, canonical ambiguity rejection, and the boundary between alias supply and provenance promotion.

- **2026-05-01**: Extended property-side provenance promotion with deterministic schema aliases, allowing Japanese lexical property tokens such as `在庫` / `合計金額` to canonicalize to `Stock` / `Total` when explicitly declared in schema metadata, and re-captured the boundary cases as successful `schema_property` / `history_*` separations.

- **2026-05-01**: Implemented the first property-side provenance promotion in `IRGenerator`: canonical schema property names can now lift `CHECK.subject_resolution` to `schema_property` / `history_subject` and `FILTER.predicate_resolution` to `schema_property` / `history_predicate` when owner uniqueness or exact-scope uniqueness is deterministically available.

- **2026-05-01**: Added `research/ir_meaning_preservation/property_side_provenance_promotion_rule.md` to define the minimal promotion rules for lifting `CHECK.subject_resolution` and `FILTER.predicate_resolution` from lexical/logic-goal retention into `schema_backed` or `history_based` property provenance.

- **2026-05-01**: Captured observed IR for `case_18_check_provenance_strength_boundary` and `case_19_filter_provenance_strength_boundary`, and added `research/ir_meaning_preservation/results/provenance_strength_boundary_observation.md` to record the current gap between expected `schema_backed/history_based` provenance and observed `explicit_subject/logic_goal` retention.

- **2026-05-01**: Extended cross-role provenance-based downstream conservatism with a first `history_based` middle policy: `CHECK.history_subject` now allows only exact-target property resolution, and `FILTER.history_predicate` / `history_collection` now avoid strong shortcut generation while still permitting generic logic-based `.Where(...)`.

- **2026-05-01**: Applied the first cross-role provenance-based downstream conservatism for `CHECK` and `FILTER`: weak `CHECK.subject_resolution` now blocks schema-backed property lifting in comparison generation, and weak `FILTER` predicate/collection provenance now stops property-aware LINQ generation with an explicit TODO instead of over-concretizing.

- **2026-05-01**: Added `research/ir_meaning_preservation/cross_role_provenance_design.md` to unify `CHECK`, `FILTER`, and `CALCULATE` under a common `resolved value + provenance + downstream policy` design, including a shared provenance-strength lattice and role-specific field mappings.

- **2026-05-01**: Added `research/ir_meaning_preservation/midterm_synthesis.md` to synthesize the current research position across baseline construction, major failure localization, provenance/resolution findings, downstream conservatism, decomposition progress, and remaining open questions.

- **2026-05-01**: Completed another orchestration-focused in-file decomposition step in `IRGenerator` by extracting `ELSE` / `END` handling, redundant `DATABASE_QUERY` suppression, and context-history appends into dedicated helpers, leaving the main generation path closer to a pure orchestration skeleton while preserving existing behavior and tests.

- **2026-05-01**: Consolidated phase-3 role-specific semantic resolution inside `IRGenerator` into a dedicated helper that applies structure-role annotation, CHECK metadata enrichment, and CALCULATE target/entity-resolution bridging before final runtime coercion, while preserving existing behavior and tests.

- **2026-05-01**: Advanced the in-file decomposition of `IRGenerator` again by extracting auto-inserted JSON deserialize/serialize node handling into local helpers for collection-input detection, current-structure append, upstream string-output checks, and JSON bridge node insertion, while preserving existing behavior and tests.

- **2026-05-01**: Advanced the in-file decomposition of `IRGenerator` by extracting final intent/runtime-role coercion and pre-emission node shaping into local helpers for runtime intent normalization, source-kind resolution, cardinality finalization, and node construction, while preserving existing behavior and tests.

- **2026-05-01**: Advanced the structural-dependency in-file decomposition inside `IRGenerator` by extracting chaining and block-attachment rules into local helpers for collection-link lookup, structural `input_link` selection, `ELSE` branch activation, and structural node attachment, while keeping the main generation flow central and preserving tests.

- **2026-05-01**: Extracted the spec-role domain from `IRGenerator` into `src/ir_generator/spec_role_rules.py`, moving specification-facing role inference behind a thin delegating wrapper while preserving existing behavior and tests.

- **2026-05-01**: Extracted the target-resolution domain from `IRGenerator` into `src/ir_generator/target_resolution.py`, moving CALCULATE target-entity ownership and schema-backed entity helpers behind thin delegating wrappers while preserving existing behavior and tests.

- **2026-05-01**: Extracted the promotion domain from `IRGenerator` into `src/ir_generator/promotion_rules.py`, moving FILTER/CALCULATE promotion helpers behind thin delegating wrappers while preserving existing behavior and tests.

- **2026-05-01**: Extracted the first module-level helper from `IRGenerator` by moving CHECK resolution logic into `src/ir_generator/check_resolution.py` and leaving thin delegating wrappers in `IRGenerator`, preserving behavior while reducing in-class bulk.

- **2026-05-01**: Extended the first in-file decomposition of `IRGenerator` by annotating the main `generate()` flow into explicit phases and marking the promotion helpers as a dedicated domain, making structure analysis, role-specific resolution, final intent coercion, and node emission easier to read.

- **2026-05-01**: Started the first in-file decomposition of `IRGenerator` by adding explicit domain headers and orchestration comments for target resolution, spec-role inference, CHECK resolution, promotion rules, and lexical baseline handling without changing behavior.

- **2026-05-01**: Added `ir_generator_decomposition_plan.md` to define a research-aligned, staged decomposition strategy for the growing `IRGenerator`, separating structural dependency, target resolution, CHECK resolution, promotion rules, and spec-role handling before any physical module split.

- **2026-05-01**: Implemented the first FILTER promotion rule in `IRGenerator`, allowing ambiguous `抽出` steps with predicate logic goals and upstream collection context to recover `LINQ/FILTER`, and observed `property`, `predicate_resolution`, and `collection_resolution` in case 16.

- **2026-05-01**: Added `filter_promotion_rule.md` to define a non-keyword-based FILTER promotion rule using ambiguous lexical evidence plus predicate logic goals and upstream collection context.

- **2026-05-01**: Added `filter_fetch_collapse_analysis.md`, tracing the FILTER failure in the provenance benchmark to an ambiguous `抽出` lexeme being classified as `FETCH` before logic-goal evidence can promote it back to `LINQ/FILTER`.

- **2026-05-01**: Implemented `CHECK.subject_resolution` in IR generation, preserving `quoted_literal` and `explicit_subject` provenance for condition subjects and updating the provenance benchmark observation accordingly.

- **2026-05-01**: Captured the first provenance-focused observations: CHECK already preserves `check_kind` and `check_subject` but lacks explicit `subject_resolution`, while FILTER still collapses to `FETCH` before predicate provenance can be attached.

- **2026-05-01**: Filled concrete expected IR for the new provenance-focused cases, fixing `predicate_resolution=logic_goal` / `collection_resolution=explicit_input_link` as the FILTER baseline and `subject_resolution=quoted_literal` / `history_subject` as the CHECK baseline.

- **2026-05-01**: Added `resolution_provenance_model.md` to generalize CALCULATE-style provenance metadata into a role-specific model for `CHECK` and `FILTER`, and added supplemental benchmark templates for filter predicate provenance and check subject provenance.

- **2026-04-30**: Split no-history entity inference from `CALCULATE` history-based entity resolution so upstream observation can preserve `entity_resolution=history_fallback`, and added `document_map.md` plus a categorized README index to keep IR research documents organized without a risky bulk move.

- **2026-04-30**: Added a `history_fallback` gap benchmark for `CALCULATE`, documenting that upstream observation still collapses some history-derived resolution into `explicit_entity` before the dedicated resolution stage runs.

- **2026-04-30**: Added `calculate_metadata_conservatism_summary.md` as a midpoint research summary showing that IR metadata now controls downstream `CALCULATE` concretization conservatively rather than serving only as observational annotations.

- **2026-04-30**: Added a unified downstream policy for `CALCULATE` `entity_resolution` values, documenting and testing that `history_fallback` allows exact-target synthesis while `ambiguous` disables cross-entity fallback and stays conservative.

- **2026-04-30**: Made downstream `CALCULATE` synthesis conservative for `entity_resolution=ambiguous`, preventing arbitrary POCO/property selection and emitting an explicit TODO stop instead of silently generating over-specific assignments.

- **2026-04-30**: Added observational `semantic_roles.entity_resolution` metadata for `CALCULATE` target-entity bridging so unique-owner and ambiguous-property cases can be distinguished without changing the resolved `target_entity` contract.

- **2026-04-30**: Added and observed an ambiguous-owner `CALCULATE` benchmark, confirming that `CALCULATE` promotion can coexist with preserving weak `target_entity` values when schema property ownership is not unique.

- **2026-04-30**: Added `calculate_target_entity_ambiguity_rule.md` to define deterministic handling for ambiguous `CALCULATE` property ownership, requiring unique schema-backed owners before lifting weak `target_entity` values.

- **2026-04-30**: Added schema-backed `CALCULATE` target-entity resolution so property ownership can lift weak `Item` targets to a unique entity without broad keyword heuristics, and added regression coverage to prevent DISPLAY-to-CALC mispromotion.

- **2026-04-30**: Improved `CHECK` subject/property resolution so `null_check` preserves identifier subjects and `comparison_check` can emit loop-scoped property conditions even when `target_entity` remains `Item`.

- **2026-04-30**: Captured observed IR and generated condition expressions for the supplemental `CHECK` cases, and documented the remaining subject/entity resolution gaps.

- **2026-04-30**: Updated condition synthesis to consume `semantic_map.check_kind`, generating `File.Exists`, null guards, and comparison expressions from IR metadata instead of falling back to generic EXISTS handling.

- **2026-04-30**: Implemented `CHECK` metadata extraction in `IRGenerator`, adding `check_kind`, `check_subject`, `expected_truth`, and comparison/source fields for condition nodes, with unit coverage for exists/null/comparison cases.

- **2026-04-30**: Added supplemental `CHECK` benchmark cases and templates for `exists_check`, `null_check`, and `comparison_check` under `research/ir_meaning_preservation/cases/`.

- **2026-04-30**: Added `research/ir_meaning_preservation/check_role_refinement.md` to define `CHECK` subtypes, required IR fields, canonical shapes, and downstream consumption order.

- **2026-04-30**: Updated `ActionSynthesizer` to consume `semantic_map.spec_role` for execution intent and candidate-role selection, and added dispatch coverage for `DESERIALIZE` and `FILTER`.

- **2026-04-30**: Implemented `spec_role` preservation in `IRGenerator` by storing it under `semantic_map`, including condition/loop overrides and auto-generated JSON serialize/deserialize nodes, and added unit coverage.

- **2026-04-30**: Added `research/ir_meaning_preservation/minimal_design_change_proposal.md` to define the smallest IR design change for preserving `spec_role` without breaking current runtime role usage.

- **2026-04-30**: Added `research/ir_meaning_preservation/focused_role_analysis.md` to isolate how `DESERIALIZE`, `FILTER`, and `CHECK` collapse into coarse runtime roles.

- **2026-04-30**: Added `research/ir_meaning_preservation/results/role_mapping_matrix.md` to compare expected `spec_role` values against observed `runtime_role` readings for the first five cases.

- **2026-04-30**: Added `spec_role` annotations to the first five expected IR case templates and aligned the role-layer definition with that comparison format.

- **2026-04-30**: Added `research/ir_meaning_preservation/role_layer_definition.md` to define separate `spec_role` and `runtime_role` layers for IR role analysis.

- **2026-04-30**: Added `research/ir_meaning_preservation/results/intent_drift_trace.md` to trace where role weakening occurs between `_analyze_step_integrated` and final IR generation.

- **2026-04-30**: Added `research/ir_meaning_preservation/intent_drift_analysis.md` to isolate recurring role/intent weakening patterns and identify likely hotspots in `IRGenerator`.

- **2026-04-30**: Added `research/ir_meaning_preservation/results/failure_mapping.md` to formally map the first five case diffs to the IR failure taxonomy.

- **2026-04-30**: Captured observed IR for the first five benchmark cases under `research/ir_meaning_preservation/results/observed_ir/` and added an initial diff summary.

- **2026-04-30**: Filled concrete draft `Expected IR` structures for the first five IR meaning-preservation benchmark case templates.

- **2026-04-30**: Added `research/ir_meaning_preservation/cases/` templates for the first five benchmark scenarios to author expected IR and record observed diffs.

- **2026-04-30**: Added `research/ir_meaning_preservation/benchmark_cases.md` to select initial IR meaning-preservation benchmark scenarios and map them to evaluation coverage.

- **2026-04-30**: Added `research/ir_meaning_preservation/evaluation.md` to define evaluation units, meaning-preservation criteria, failure taxonomy, and phase-1 exit criteria for IR research.

- **2026-04-30**: Created `research/` as a dedicated workspace for foundational research and added initial documentation for `ir_meaning_preservation`.

- **2026-04-30**: Added `AIFiles/FOUNDATIONAL_RESEARCH_AREAS.md` to summarize foundational research themes based on the project charter and development conventions.

- **2026-04-21**: Switched default chiVe model from `chive-1.3-mc5` to `chive-1.3-mc90`, changed vector cache default to full load (`v0`), updated fetch/convert scripts and cache checks, and validated with real-model vector tests.

- **2026-04-09**: CodeBuilder blueprints now use synthesized input_defs to omit parameters when Input is none.

- **2026-04-09**: Normalized Input/Output "none" handling in StructuredDesignParser to avoid invalid parameter types.

- **2026-04-09**: Stripped backticks from Input/Output fields in StructuredDesignParser to prevent invalid codegen types.

- **2026-04-09**: Fixed inference metadata block replacement to preserve sections after "### Inference Metadata".

- **2026-04-09**: Improved inference handling for SQL-backed steps and DISPLAY output typing in design_inference.

- **2026-04-09**: Fixed inference write-back to preserve numbered list prefixes in Core Logic.

- **2026-04-09**: Enabled semantic candidate search over action_patterns/canonical templates for deterministic inference in DesignOpsResolver.

- **2026-04-09**: Implemented infer-then-freeze engine in source (design_parser/design_inference) and wired into design generation flow.

- **2026-04-09**: Added confidence thresholds and blocking rules for infer-then-freeze in generate_from_design_dataflow.md.

- **2026-04-09**: Added infer-then-freeze scope and ordering rules to generate_from_design_dataflow.md and referenced scope in design_parser.design.md.

- **2026-04-09**: Documented implementation placement for infer-then-freeze in generate_from_design_dataflow.md and clarified design_parser responsibility boundary.

- **2026-04-09**: Documented fingerprint calculation for infer-then-freeze in generate_from_design_dataflow.md and design_parser.design.md.

- **2026-04-09**: Added infer-then-freeze rules and embedding format to generate_from_design_dataflow.md and design_parser.design.md.

- **2026-04-09**: Added infer-then-freeze note to design_parser.design.md for deterministic metadata persistence.

- **2026-04-09**: Documented infer-then-freeze design inference flow in generate_from_design_dataflow.md.

- **2026-04-09**: Added deterministic “infer-then-freeze” policy to design conventions for natural-language specs.

- **2026-04-08**: Updated autonomous_learning and autonomous_aligner design docs to reflect current runtime behavior.

- **2026-04-08**: Updated code_synthesis and code_verification design docs to reflect current runtime behavior.

- **2026-04-08**: Updated semantic_search and vector_engine design docs to reflect current runtime behavior.

- **2026-04-08**: Updated task_manager, clarification_manager, and response_generator design docs to reflect current runtime behavior.

- **2026-04-08**: Updated pipeline_core and intent_detector design docs to reflect current runtime behavior (vector loading, clarification thresholds, intent scoring/boosts).

- **2026-04-06**: Reorganized scripts into categorized subfolders and updated docs/README references; added `run_unit_smoke.py` runner and vector cache required test; integrated chiVe cache conversion script and enforced cache-only loading; unified vector_db storage under `resources/vectors/vector_db`; removed JLPT input pipeline and user_dic usage; updated JMDict pipeline to DB-only; updated blueprint cache path to `cache/blueprints/<run_id>/blueprint.json`.

- **2026-04-03**: Removed '1件' wording from service get defaults and OrdersProject spec to eliminate numeric_goal_missing warnings; regenerated Orders/MinimalCrud/Notes and tests passed.

- **2026-04-03**: Updated design_parser/test_generator/utils design docs to reflect current behavior; project consistency validation now passes.

- **2026-04-02**: Added missing design docs for new code_generation helpers (audit/spec/controller/naming/repo/service) and reran project consistency validation.

- **2026-04-02**: Reordered delete row-count checks to align with numeric-goal ordering in repo design docs (>=1 then ==0).
- **2026-04-02**: Split repository generation logic out of project_generator into code_generation/repo_generation.py (RepoGenerationHelper).
- **2026-04-02**: Split service generation logic out of project_generator into code_generation/service_generation.py (ServiceGenerationHelper).
- **2026-04-02**: Split spec parsing helpers into code_generation/spec_helpers.py (SpecHelpers).
- **2026-04-02**: Split audit helpers into code_generation/audit_helpers.py (AuditHelpers), leaving factories in project_generator.
- **2026-04-02**: Split controller generation into code_generation/controller_generation.py (ControllerGenerationHelper).
- **2026-04-02**: Split spec completion into code_generation/spec_completion.py (SpecCompletionHelper).
- **2026-04-02**: Split naming/typing/mapping utilities into code_generation/naming_helpers.py (NamingHelpers).
- **2026-04-02**: Rewired project_generator defaults/spec completion and controller synthesis to delegated helpers without adding new test modules.
- **2026-04-02**: Repo freeform update/delete now emits deterministic row-count checks (rows==0 / rows>=1) to satisfy numeric goals.
- **2026-04-02**: Added explicit-tag-based service synthesis that maps explicit intents to deterministic CRUD steps (opt-in via USE_SERVICE_FREEFORM=1).
- **2026-04-02**: Added deterministic post-processing for repository freeform synthesis (strip await/Async calls and map input_1/input_2 to method parameters).
- **2026-04-02**: Disabled service freeform synthesis by default; it is now opt-in via USE_SERVICE_FREEFORM=1 to prevent invalid codegen.
- **2026-04-02**: Freeform project synthesis now requires explicit intent/semantic roles per step; otherwise it falls back to structured CRUD to avoid heuristic code.
- **2026-04-02**: Project generation now builds freeform structured specs from explicit design tags (ops/semantic_roles/data_source) instead of plain text steps.
- **2026-04-02**: Added LiteTodoProject minimal Human Spec scenario, allowed core_logic bullet parsing in ProjectSpecParser, and generated LiteTodoProject for alignment review.
- **2026-04-02**: Improved audit determinism (LogicAuditor operator/ordering checks), stabilized UKB candidate sorting, switched CodeBuilder to use prebuilt exe for faster generation, and updated SampleProject design wording to avoid numeric goal false positives.
- **2026-04-02**: Added nullable return notation guidance to the Human Spec design document template.
- **2026-04-02**: Added overall review report for generated projects (Sample/Orders/Minimal/Notes) confirming design alignment.
- **2026-04-01**: Regenerated SampleProject/OrdersProject after nullable signature hinting; tests passed (34 each).
- **2026-04-01**: Parsed nullable return hints from module method signatures (last-colon split fix); regenerated NotesProject/MinimalCrudProject and verified tests pass.
- **2026-04-01**: Limited UpdatedAt SQL auto-injection to auto-completed specs only; regenerated OrdersProject and verified tests pass.
- **2026-04-01**: Added NotesProject minimal Human Spec scenario and verified generation/tests (8 passing).
- **2026-04-01**: Added a minimal CRUD Human Spec example to the design document template.
- **2026-04-01**: Avoided default CRUD completion when method_specs already define the CRUD kind; regenerated OrdersProject/SampleProject and verified tests pass (34 each).
- **2026-04-01**: Fixed repository insert generation to include CreatedAt in SQL parameters and returned entity when present; regeneration verified with tests passing.
- **2026-04-01**: Added default DTO↔Entity same-name mapping when mappings are omitted; verified MinimalCrudProject generation and tests (8 passing).
- **2026-04-01**: Simplified the Human Spec design document template to reduce authoring burden; clarified that Machine Spec is auto-completed.
- **2026-03-31**: Added internal CRUD method spec completion (service steps/core logic + repo SQL/steps) and documented two-layer design guidance in conventions and project overview.
- **2026-03-31**: Regenerated SampleProject/OrdersProject and ran dotnet test; 34 tests passed in each project (net10.0 preview warning only).
- **2026-03-31**: Converted SampleProject/OrdersProject service Test Cases to structured JSON and regenerated both projects to emit test-case-based service tests.
- **2026-03-31**: Added structured JSON Test Cases parsing and generation for service tests; updated related design docs.
- **2026-03-31**: Regenerated OrdersProject/SampleProject with enhanced service tests and re-ran dotnet test (16 tests each) successfully.
- **2026-03-31**: Enhanced service test generation to include happy-path CRUD tests (create/get/update/delete success) and added GetMethod to test context.
- **2026-03-31**: Ran dotnet test for OrdersProject and SampleProject (net10.0 preview) to validate generated tests.
- **2026-03-31**: Updated utils design doc to reflect LogicAuditor bracket-tag stripping and operator-phrase precedence.
- **2026-03-31**: Updated code_synthesis design docs to reflect transform `consumes` metadata and reachability audit consumption rules.
- **2026-03-31**: Updated code_generation design docs (project_generator, validation_renderer) to reflect method-name priority, route-base inference, and controller null-guard behavior.
- **2026-03-31**: Removed generated method_name_override_check project output while keeping the design spec.
- **2026-03-31**: Controller validation guards now include null request checks (BadRequest) for create/update actions; verified in method_name_override_check regeneration.
- **2026-03-31**: Updated method_name_override_check design to explicitly include UpdatedAt refresh on update and SQL update column list; regenerated project to match.
- **2026-03-31**: Project generator now derives controller route base from explicit routes to avoid double path segments; verified with method_name_override_check regeneration.
- **2026-03-31**: Aligned method_name_override_check CatalogController routes with design (`/catalog` base + `{id}` actions).
- **2026-03-31**: Added `method_name_override_check` design and verified explicit service/repo method names propagate into generated services/repos/tests; fixed CRUD template override to work even without a template block.
- **2026-03-31**: Project generator now prioritizes explicit service/repo method names from design steps (service.* / repo.*) and propagates them into tests via CRUD template override.
- **2026-03-31**: OrdersProject regen still outputs `GetInventory`; restored `GetInventoryItems` in service/interface/controller/tests to match design spec after full project regeneration.
- **2026-03-31**: Regeneration reset OrdersProject inventory list method name; restored `GetInventoryItems` in service/interface/controller/tests to align with design spec.
- **2026-03-31**: Reachability audit now honors explicit `consumes` metadata for raw transform statements; transform ops now record consumed inputs to avoid false F-2 warnings (e.g., StdinToStdoutTransform).
- **2026-03-31**: Updated InputLinkDropRepro design output to string? and confirmed F-2 warning cleared after regeneration.
- **2026-03-31**: Split CalculateOrderDiscount conditions to explicit Total/CustomerType checks and ensured else branch covers Total <= 5000.
- **2026-03-31**: Updated CsvSalesAggregation design output to string? to match null-on-error behavior.
- **2026-03-31**: Updated StateUpdatePersist design output to Task<bool> to match async implementation.
- **2026-03-31**: Updated DailyInventorySync design output to Task<int> to match async implementation.
- **2026-03-31**: Updated SyncExternalData design output to Task<bool> to match async implementation.
- **2026-03-31**: Updated SecureOrderProcessing output to Task<bool> and enforced Total > 0 filter via semantic_roles.
- **2026-03-31**: Clarified UserReportGenerator output to allow null on failure and treated return raw statements as sinks in reachability audit.
- **2026-03-31**: Renamed Inventory service list method to GetInventoryItems to match OrdersProject design spec.
- **2026-03-31**: Updated FetchProductInventory design output to Task<bool> to match async implementation.
- **2026-03-31**: LogicAuditor now strips bracket tags before extracting logic goals; ComplexLinqSearch LINQ steps split for explicit property targeting.
- **2026-03-31**: Reachability audit now treats raw statements with out_var as consuming sources to reduce false-positive F-2 warnings.
- **2026-03-31**: Aligned ProcessActiveUsers purpose with actual display-only behavior.
- **2026-03-31**: LogicAuditor operator matching now honors explicit phrase containment for deterministic comparison operators.
- **2026-03-31**: Allowed explicit semantic_roles property override for LINQ property resolution and updated ProcessActiveUsers design to specify Price.
- **2026-03-31**: Clarified ProcessActiveUsers design to return false on read failure and true on success.
- **2026-03-31**: Verified ProcessActiveUsers synthesis output uses join-based collection display (string.Join + Select) for display_names.
- **2026-03-31**: Adjusted method store spec/validator to separate base vs extended keys and added role enrichment from capability map.
- **2026-03-31**: Expanded method store entries used by failed scenarios (file IO, JSON deserialize, LINQ, console output) with definitions, usings, and side-effect flags.
- **2026-03-31**: Added method store entry for `System.String.Join` to support collection display synthesis.
- **2026-03-31**: Added `System.Console.WriteLine(string format, params object[] args)` to method store for formatted collection output.
- **2026-03-31**: Added `System.String.Join` and `Console.WriteLine` param roles to `method_capability_map.json` for collection display intent support.
- **2026-03-31**: DISPLAY `display_names` now prefers `string.Join` + `Select` for collection output instead of per-item `foreach`.
- **2026-03-31**: Updated `display_transform_ops` design doc to reflect `display_names` join-based output.
- **2026-03-31**: Reviewed and refreshed code_synthesis design docs to align timestamps with current implementations.
- **2026-03-31**: generate_from_design now initializes VectorEngine for method store synthesis runs.
- **2026-03-31**: Updated code_synthesis design doc review notes after action_handlers import fix.
- **2026-03-31**: CodeSynthesizer now passes VectorEngine/MorphAnalyzer to StructuralMemory.
- **2026-03-31**: StructuralMemory indexing now skips non-string property names to avoid unhashable errors.
- **2026-03-31**: StructuralMemory normalizes non-string class/method/function names to prevent indexing failures.
- **2026-03-31**: StructuralMemory now JSON-normalizes dict/list identifiers to avoid unhashable ids during indexing.
- **2026-03-31**: SemanticSearchBase vectorization now converts dict tokens to surface strings.
- **2026-03-31**: Added `scripts/validate_method_store.py` and updated ops checklist for method store validation.
- **2026-03-31**: Updated `docs/project_overview.md` with method store artifacts and spec pointer.
- **2026-03-31**: Added `docs/method_store_spec.md` to document method store structure.
- **2026-03-31**: Added `docs/ops_checklist.md` to standardize post-change validation steps.
- **2026-03-31**: Expanded thin design docs (config, safety, context_utils, base_detector, session_manager) to align structure and detail.
- **2026-03-31**: Normalized design doc dependency names (removed `src.` prefixes) across core modules.
- **2026-03-30**: Added `docs/priority_issues.md` to track prioritized issues.
- **2026-03-30**: Renamed `action_handlers.utils` to `action_utils` to avoid module name collision and updated references.
- **2026-03-30**: Added missing design docs for sandbox/test/text utility submodules.
- **2026-03-30**: Added missing design docs for `code_synthesis/action_handlers` submodules.
- **2026-03-30**: Added missing design docs for project generation submodules (project/spec parsing, synthesis pipeline, renderers).
- **2026-03-30**: Updated missing/outdated design documents across core flows (code generation, verification, dialogue, search) and registered `code_generation` in `ai_project_map.json`.
- **2026-03-26**: Added `docs/project_overview.md` to summarize entry points, core flows, and module map.
- **2026-03-26**: Extended `docs/project_overview.md` with ActionExecutor action map.
- **2026-03-26**: Added Intent routing and task definition overview to `docs/project_overview.md`.
- **2026-03-18**: generate_from_design の安全コマンド制約を追加
    - **CMD_RUN**: `semantic_roles.command` の先頭トークンが `safety_policy.safe_commands` に含まれるか検証。
    - **狙い**: 設計書の意図に沿った安全なコマンド実行だけを許可。
- **2026-03-18**: DemoGen 出力を全件再生成
    - **方針**: 生成済みコードの直接修正ではなく設計書から再生成。
    - **対象**: `scenarios/*.design.md` と `SampleApp.design.md` から `DemoGen*.cs` を再生成。
- **2026-03-18**: display_names の反映経路を修正
    - **ActionSynthesizer**: `semantic_roles.ops` を直接参照し、単体DISPLAYでも `display_names` を適用。
    - **Design**: BatchProcessProducts に `ops:display_names` を追加。
    - **出力**: DemoGenProcessActiveUsers / DemoGenBatchProcessProducts が名前のみを表示。
- **2026-03-19**: SemanticBinder のプロパティ解決をドメイン辞書に移行
    - **優先マップ削除**: `_resolve_prop` のハードコード辞書を撤廃。
    - **Domain Dictionary**: `resources/domain_dictionary.json` を読み込み、同義語ベースで解決。
    - **影響**: キーワードの外部化により場当たり的マッピングを減らす。
    - **検証**: `tests.unit.test_regression_scenarios` を通過。
- **2026-03-19**: 通知/数量/日時キーワードをドメイン辞書へ外部化
    - **Domain Dictionary**: `tags.notification` / `tags.quantity` / `tags.datetime_now` を追加。
    - **ActionSynthesizer**: 直書きキーワード判定を `domain_dictionary.json` 参照に置換。
    - **検証**: `tests.unit.test_regression_scenarios` を通過。
- **2026-03-19**: 直書きキーワードの外部化を拡張
    - **Domain Dictionary**: 更新/集計/UTC/最終/HTTP書き込み/永続化/ヒューリスティック系のタグを追加。
    - **ActionSynthesizer**: 更新/集計/UTC/最終の判定を tags 参照に置換。
    - **SemanticBinder**: HTTP書き込み判定と persist 意図判定を tags 参照に置換。
    - **CodeSynthesizer**: 構造化前のヒューリスティック判定を tags 参照に置換。
    - **検証**: `tests.unit.test_regression_scenarios` を通過。
- **2026-03-19**: CALCの数量/価格/日時推論をsemantic_roles優先に変更
    - **ActionSynthesizer**: `quantity/price` のsemantic_rolesを優先して小計式を生成し、テキストタグ依存を抑制。
    - **ActionSynthesizer**: `datetime` が指定されている場合はタグ判定で上書きしないよう調整。
- **2026-03-19**: TypeSystem の型解析を ActionSynthesizer で活用
    - **TypeSystem**: `unwrap_task_type` / `extract_generic_inner` を追加。
    - **ActionSynthesizer**: 独自の型解析メソッドを削除し TypeSystem に統一。
- **2026-03-19**: SemanticBinder のプロパティ解決を SymbolMatcher へ統合
    - **SemanticBinder**: `domain_mappings` 経由の独自解決を廃止し、`SymbolMatcher.find_best_match` を優先。
    - **SemanticBinder**: ヒント未指定時の数値プロパティ選定は型情報のみで決定（キーワード依存を縮小）。
- **2026-03-19**: UnifiedKnowledgeBase のドメイン知識を SymbolMatcher に統合
    - **CanonicalKnowledge**: `domain_mappings` を追加し、標準マッピングをUKBに集約。
    - **SymbolMatcher**: ハードコードされた標準マッピングを撤廃し、UKB＋domain_dictionary を優先。
- **2026-03-19**: URL/SQLパラメータ解析を共通ユーティリティに統合
    - **Utils**: `src/utils/text_parser.py` を追加し URL/SQL パラメータ抽出を集約。
    - **SemanticBinder/ActionSynthesizer/IRGenerator**: 重複ロジックを共通関数に委譲。
- **2026-03-19**: URL抽出の重複を削減し、SQLパラメータ抽出を統一
    - **SemanticAnalyzer**: URL抽出を `text_parser.extract_urls` に委譲。
    - **BlueprintAssembler**: SQLパラメータ抽出を `text_parser.extract_sql_params` に統一。
- **2026-03-19**: 監査v3に沿ってユーティリティ/UKBへ委譲
    - **ActionSynthesizer/SemanticBinder/IRGenerator**: 重複ヘルパを削除し `text_parser` / `TypeSystem` / `UKB` に統一。
    - **CanonicalKnowledge**: `structural_keywords` / `intent_keywords` / `intent_role_keywords` / `role_synonyms` を追加。
- **2026-03-19**: Transform Ops とロールスコアのハードコードを解消
    - **CanonicalKnowledge**: `transform_ops` / `role_scoring` を追加。
    - **ActionSynthesizer**: Transform ops の実装をUKB定義に委譲。
    - **SemanticBinder**: roleスコアのマジックナンバーをUKB設定へ移動。
- **2026-03-19**: ヒューリスティックなエンティティ判定を外部化
    - **Domain Dictionary**: `heuristic_entity_*` タグを追加。
    - **CodeSynthesizer**: `User/Product/Inventory/Order` 判定を tags 参照に置換。
    - **SemanticBinder**: `http_write` 判定のタグ参照を安定化。
    - **検証**: `tests.unit.test_regression_scenarios` を通過。
- **2026-03-18**: HTTP JSONの例外保護とAPIキー利用を反映
    - **DailyInventorySync**: `use_api_key_header` を適用し、HTTPヘッダへ `X-API-Key` を付与。
    - **DailyInventorySync/SyncExternalData**: JSONデシリアライズを try/catch で保護。
    - **検証**: `tests.unit.test_regression_scenarios` を通過。
- **2026-03-18**: SampleApp の入力反映と生成コードの安全化
    - **Design**: SampleApp の SQL を `@userId` で入力反映。
    - **生成**: BatchProcessProducts の JSON 例外保護、StateUpdatePersist の FirstOrDefault ガードを反映。
    - **検証**: `tests.unit.test_regression_scenarios` を通過。
- **2026-03-18**: EXISTS 判定を明示生成して未実装例外を回避
    - **Condition**: collection の存在判定を `Any()` で生成。
    - **検証**: `SampleApp.design.md` の再生成を確認、`tests.unit.test_regression_scenarios` を通過。
- **2026-03-18**: 小計計算の数量反映とエンティティ補完を改善
    - **EntitySchema**: Product に `Quantity` を追加。
    - **CALC**: 「数量」指示がある場合、`Price * Quantity` を優先生成。
    - **EntityFallback**: entity_schema からのプロパティ補完を追加。
    - **検証**: `tests.unit.test_regression_scenarios` を通過。
- **2026-03-18**: 生成コードのデータ利用・表示・HTTPの整合を改善
    - **HTTP**: `use_api_key_header` ops で `X-API-Key` を付与可能にした。
    - **DISPLAY**: `display_names` ops で POCO の Name 一覧を表示可能にした。
    - **CALC**: コレクションに対する更新は `FirstOrDefault` + null ガードで安全化。
    - **IR**: PERSIST の input_link を input_refs 優先で補正。
- **2026-03-18**: safe_commands と CMD_RUN の設計書ガイドを強化
    - **SafetyPolicy**: `safe_commands` に `py` を追加。
    - **Conventions**: CMD_RUN の `semantic_roles.command` 指定ルールを追記。
- **2026-03-18**: JSON_DESERIALIZE の異常系ガード検証を追加
    - **テスト**: JSON_DESERIALIZE が try/catch で包まれることを回帰テスト化。
    - **検証**: `tests.unit.test_json_deserialize_guard` を通過。
- **2026-03-18**: JSON_DESERIALIZE の try/catch 包括で input_ref 監査を維持
    - **StatementBuilder**: try/catch の raw ステートメントに出力変数情報を保持し、auto-node の出力認識を維持。
    - **検証**: `tests.unit.test_regression_scenarios` を通過。
- **2026-03-18**: DISPLAY通知の input_link を抑制して根本解消
    - **IRGenerator**: 通知系 DISPLAY は input_link を付与しない。
    - **回帰**: UserReportGenerator / CalculateOrderDiscount を含む全回帰テストが通過。
- **2026-03-18**: input_link / input_ref の自動ノード・通知判定を補正
    - **input_ref**: auto-node (例: `step_1_json`) の出力利用で ref 充足とみなす。
    - **input_link**: DISPLAY通知は input_link 監査をスキップ。
    - **PERSIST**: 直前が文字列出力の場合は input_link を直近ノードに寄せる。
- **2026-03-18**: 回帰テスト対象を拡充（中優先3本）
    - **追加**: InputLinkDropRepro を専用検出テストへ移動。
    - **追加**: ProcessActiveUsers / ComplexLinqSearch を回帰テストに追加。
- **2026-03-18**: 回帰テスト対象を拡充（高優先3本）
    - **追加**: SyncExternalData / FetchProductInventory / BatchProcessProducts
- **2026-03-18**: 代表シナリオの回帰テストを追加
    - **対象**: EnvConfigToConsole / StdinToStdoutTransform / CsvSalesAggregation / DailyInventorySync
    - **検証**: SpecAuditor で問題なしを確認。
- **2026-03-18**: generate_from_design の前段検証を追加拡張
    - **設計書名整合**: `.design.md` のベース名と module_name が一致することを検証。
- **2026-03-18**: NuGetClient の利用整理
    - **MethodHarvester**: config_manager を渡して依存マップの保存先を統一。
- **2026-03-18**: generate_from_design の前段検証を強化
    - **設計書**: `.design.md` サフィックスを必須化。
    - **出力**: C# の拡張子 `.cs` を検証。
    - **規約**: banned_patterns を module_name / path / source_ref へ適用。
- **2026-03-18**: SpecAuditor の誤検知を抑制（ENV/STDIN/CSV）
    - **STDIN**: FETCH の raw ステートメントに intent を付与して intent 未検出を解消。
    - **input_refs**: 下流ステップでの利用を許容し、ENV系の誤検知を解消。
    - **input_link**: loop 直後の集計/変換で他の上流出力を使うケースを許容。
- **2026-03-18**: Replanner の収束ガードを入力リンク/参照系で緩和
    - **狙い**: SPEC_INPUT_LINK_UNUSED / SPEC_INPUT_REF_UNUSED の再計画が繰り返しでも収束エラーにしない。
    - **検証**: EnvConfigToConsole の再計画で convergence error が出ないことを確認。
- **2026-03-18**: generate_from_design の再計画時に input_defs を引き継ぐよう修正
    - **修正**: 再生成ループでも入力変数が参照できるようにして、ファイルパスのリテラル化を防止。
    - **検証**: CsvSalesAggregation の `File.ReadAllText(input_path)` / `WriteAllText(output_path, ...)` を確認。
- **2026-03-18**: 非DBシナリオの回帰検証を実施
    - **対象**: CsvSalesAggregation / EnvConfigToConsole / StdinToStdoutTransform / EphemeralCalculation を生成検証。
    - **検知**: CSVで入出力パスが文字列リテラル化、input_link/input_ref 由来の監査警告が残存。
- **2026-03-18**: IRGenerator の input_link 優先ルールをユニットテスト化
    - **テスト追加**: 直近のコレクション出力が DISPLAY 入力に選ばれることを検証。
- **2026-03-18**: input_link がコレクション出力を優先参照するよう調整
    - **IRGenerator**: LOOP/LINQ/PERSIST/DISPLAY/TRANSFORM/CALC の入力は直近コレクションノードを優先。
    - **検証**: DailyInventorySync で input_link と foreach の連携を確認。
- **2026-03-18**: 監査レポートの導線を追加
    - **データフロー文書**: テンプレートと索引へのリンクを追記。
- **2026-03-18**: 監査レポート索引を追加
    - **一覧化**: generate_from_design の監査レポートを日付別に整理。
- **2026-03-18**: loop内input_linkの安定性テストを追加
    - **inner/parent**: 親ループで上流コレクションを消費し、innerがアイテムを使うケースをテスト化。
- **2026-03-18**: 監査レポートを追加
    - **ProcessActiveUsers**: generate_from_design の監査結果をレポート化。
- **2026-03-18**: 監査レポートを追加
    - **DailyInventorySync**: generate_from_design の監査結果をレポート化。
- **2026-03-18**: 監査レポートを作成
    - **CalculateOrderDiscount**: generate_from_design の監査結果をレポート化。
- **2026-03-18**: 監査レポートのテンプレートを追加
    - **定型化**: generate_from_design の監査結果を整理するためのテンプレートを追加。
- **2026-03-18**: CALC/通知DISPLAYの監査精度を改善
    - **CALC意図付与**: 計算ノードの生成ステートメントに intent を後付けして監査誤検知を解消。
    - **通知のinput_refs除外**: DISPLAY通知に semantic_role を付与し、input_refs監査から除外。
- **2026-03-18**: SpecAuditor のテストを追加
    - **意図整合**: `SPEC_INTENT_NOT_EMITTED` の検出/許容パターンをテスト化。
    - **input_refs**: 未使用検出と自己参照除外をテスト化。
    - **loop内input_link**: 親ループ参照を考慮した判定をテスト化。
- **2026-03-18**: 監査強化のドキュメントを更新
    - **SpecAuditorの拡張内容**: intent整合、input_refs到達性、loop内input_link扱いをデータフロー文書に追記。
- **2026-03-18**: input_link 監査のループ内判定を改善
    - **親ループ考慮**: `*_inner` ノードは親ループの参照で上流変数が使われていれば OK とする。
- **2026-03-18**: input_refs 到達性の監査を追加
    - **SpecAuditor拡張**: `input_refs` で宣言された上流出力が当該ステップで使用されるかをチェック。
    - **自己参照除外**: `input_refs` が自身を指す場合は誤検知を避けて除外。
- **2026-03-18**: LINQ フィルタ生成の意図伝播を補完
    - **LINQ raw文**: `Where(...).ToList()` 生成に intent を付与し、意図監査の誤検知を解消。
- **2026-03-18**: TRANSFORM/CALC の意図伝播を補完
    - **CSV集計/変換**: CSV集計と変換オペレーションのステートメントに intent を付与し、監査の誤検知を解消。
- **2026-03-18**: SpecAuditor の意図整合チェックを拡張（P2-1）
    - **意図の反映検査**: IR ノードの intent が生成ステートメントに反映されているかを監査。
    - **ステートメント意図付与**: try/catch・loop・condition・return のステートメントに intent を伝播。
- **2026-03-18**: CompilationVerifier の依存復元を安定化
    - **fast-track修正**: 依存や csproj 変更時は `--no-restore` を使わず、必要な restore を確実に実行。
    - **ベースサンドボックス検査**: 既存 csproj の依存整合性を確認し、不足時は再初期化。
    - **バージョン上書き**: 生成側の依存バージョンを優先的に反映。
- **2026-03-18**: NuGet依存解決の一元化（P1-1）
    - **NuGetClientに集約**: using→依存解決をNuGetClient側の決定的ヘルパに移譲し、重複排除とキャッシュ保存を統一。
    - **検証側の依存整理**: CompilationVerifierの依存は小さな明示デフォルト＋生成側から渡された依存のみで構成。
- **2026-03-18**: JSON_DESERIALIZE候補の副作用再検証を実施
    - **複数シナリオ確認**: Batch/Order/Linq/Inventory/User系のJSON変換が正常出力されることを確認。
- **2026-03-18**: JSON_DESERIALIZE 候補を抑制
    - **HTN除外とJsonSerializer限定**: JSON_DESERIALIZEではHTN候補を除外し、JsonSerializer系のみ許可。
- **2026-03-18**: JSON_DESERIALIZE の入力ガードを追加
    - **string以外を抑止**: content が string でない場合は JSON_DESERIALIZE を候補から除外。
- **2026-03-18**: JSON_DESERIALIZE の型推論を強化
    - **コレクション型の抽出**: `List<T>`/`IEnumerable<T>`/`T[]` から内側型を推定し、JSONデシリアライズの型を安定化。
- **2026-03-18**: HTTP/JSON 生成の重複呼び出しを回避
    - **call引数の正規化**: 既に `(...)` を含むメソッドには args を付与しないよう正規化。
- **2026-03-18**: using と logger 注入を最小化
    - **usingの絞り込み**: 生成コード内の参照に基づき必要な名前空間のみ付与。
    - **loggerの条件化**: _logger が使われない場合は Console.Error にフォールバック。
- **2026-03-18**: 生成POCOの不要注入を抑止
    - **Productの条件付与**: 実際に参照される場合のみ `Product` クラスを追加。
- **2026-03-18**: 生成候補のフィルタリングを調整し、環境変数やCSVの誤合成を抑止
    - **env 取得の誤経路排除**: `source_kind=env` では JSON/ファイル系のHTN候補を除外し、Environment系メソッドに限定。
    - **JSON不要時のHTN抑制**: `output_type` や `.json` パス判定に基づき、不要な JSON_DESERIALIZE ステップを回避。
    - **無効メソッド名の除外**: 空白を含むメソッド名を候補から除外。
- **2026-03-17**: 生成パイプラインの入力連携とSQLパラメータ補正を強化
    - **RETURNの入力リンク抑制**: 返却リテラルで上流参照がない場合、`input_link` を外して不要な `SPEC_INPUT_LINK_UNUSED` を回避。
    - **DBクエリのnullパラメータ回避**: `@param` を含むSQLで `null` が渡る場合、入力引数を優先して匿名オブジェクトに補正。
    - **input_defs の伝搬**: 合成パスに `input_defs` を保持し、後段バインディングの入力参照を安定化。
    - **POCO生成の型抽出改善**: 例外ラップ時のホイスト宣言に `var_type` を保持し、未定義型の漏れを抑止。
    - **ユニットテスト追加**: RETURNの入力リンク抑制とSQLパラメータの入力バインドを検証。
- **2026-03-17**: LOGIC_STRING_MISMATCH の誤検知を抑止
    - **識別子の許容**: 文字列ゴールが識別子の場合、コード内に未引用でも存在すれば一致扱いに変更。
    - **ユニットテスト追加**: `Id` のような識別子がSQL内に出現するケースを検証。

- **2026-03-17**: StructuredSpec由来の制御構造とDB意図の整合性を修正
    - **LOOPのcardinality固定**: `LOOP` ノードは `COLLECTION` を維持し、単数化の自動変換を回避。
    - **DB意図のエビデンス判定**: `source_kind` を直接参照し、DB根拠がない場合のみ `FETCH` に降格。

- **2026-03-17**: MethodStoreの互換 setter を追加
    - **後方互換**: `methods` プロパティに setter を追加し、テストからの初期化を許容。

- **2026-03-17**: CodeSynthesizer の後方互換を改善
    - **synthesize 互換API**: 旧インターフェースを復活し、StructuredSpecへ自動変換。
    - **CodeBuilder不在時の簡易生成**: テスト環境向けにヒューリスティック出力を追加。

- **2026-03-17**: 比較演算子の型ミスマッチ検出を拡張
    - **LogicAuditor 強化**: 数値目標に対して `StartsWith/Contains` が使われている場合をミスマッチとして検出。
    - **ユニットテスト追加**: 数値目標での文字列演算誤用を検知できることを確認。

- **2026-03-17**: LOOP/CONDITIONの入力リンク監査を改善
    - **SpecAuditorの検出強化**: `foreach` の `source` と `if` の `condition` を監査対象に含め、誤検出を抑止。
    - **ユニットテスト追加**: ループと条件分岐で upstream 変数が使われることを検証。
    - **シナリオ再検証**: `CalculateOrderDiscount` で `SPEC_INPUT_LINK_UNUSED` が解消されることを確認。

- **2026-03-17**: logger未使用時の依存付与を抑止するテストを追加
    - **BlueprintAssembler テスト**: `_logger` 未参照で `Microsoft.Extensions.Logging` を追加しないことを検証。

- **2026-03-17**: 数値比較の文字列化を抑止
    - **StartsWith回避**: 数値プロパティに対する比較は識別子/数値のみ許可し、非数値は数値比較にフォールバック。
    - **ユニットテスト追加**: `{input}` が `input_1` に解決される数値比較で `StartsWith` が出ないことを検証。

- **2026-03-17**: {input} プレースホルダの照合テストを追加
    - **LogicAuditor テスト**: `input_1` への解決を許容するケースと未解決ケースをユニットテスト化。

- **2026-03-17**: 入力プレースホルダの整合性チェックを改善
    - **{input} の許容判定**: `{input}` が入力引数 (`input_1` など) に解決されている場合は不一致扱いしないように修正。
    - **リプラン抑止**: 正しい `Points > input_1` の生成が LOGIC_VALUE_MISMATCH によって壊される問題を回避。

- **2026-03-17**: ILogger 依存の追加と不要依存の抑制を両立
    - **Logger使用時のみ依存追加**: `_logger` の参照検出で `Microsoft.Extensions.Logging` を追加。
    - **依存解決の精度改善**: 生成コードの `using` を依存解決に反映して NuGet 解決漏れを防止。

- **2026-03-17**: PERSIST前の自動シリアライズ判定を改善
    - **DISPLAY出力の型推定**: DISPLAY意図の出力型を `string` として扱い、上流が文字列のときは余計な `_ser` ノードを抑止。
    - **input_link参照の強化**: 直前ノードの出力型/意図から `input_is_string` を判定し、context_historyの不足を補完。
    - **履歴拡張**: `context_history` に `output_type` と `source_kind` を保持し、下流判定の精度を向上。

- **2026-03-17**: UserReportGenerator のポイント条件フィルタを明示化
    - **LINQ ops の追加**: `filter_points_gt_input` を導入し、入力値に基づくポイント抽出を決定的に生成。
    - **User スキーマ拡張**: `Points` プロパティを `entity_schema.json` に追加。
    - **設計書の明示化と検証**: `UserReportGenerator.design.md` に ops を追加し、ユニットテストで `Points > input_1` を検証。

- **2026-03-17**: 生成時のロジック不整合の警告を常時表示
    - **ReasonAnalyzer の活用**: `generate_from_design.py` でリトライ未使用時でもロジック不整合ヒントを出力。

- **2026-03-17**: SpecAuditor に input_link のデータフロー検査を追加
    - **上流出力の未使用検出**: `input_link` の出力変数が下流で使われない場合に `SPEC_INPUT_LINK_UNUSED` を報告。

- **2026-03-17**: input_link 検査の精度強化
    - **type_to_vars の活用**: 上流出力の推定に `type_to_vars` を併用し、検出漏れを低減。
    - **ノードIDの補完検索**: `step_1` と `step_1_1` のような派生IDも追跡。
    - **assign対応**: `assign` ステートメントからの参照も検出対象に追加。

- **2026-03-17**: SPEC_INPUT_LINK_UNUSED を生成失敗扱いに昇格
    - **ブロッキング判定**: リトライ無しの生成で検出された場合は即失敗として停止。

- **2026-03-17**: SPEC_INPUT_LINK_UNUSED をリトライ時もブロッキング扱い
    - **強制リプラン**: リトライ中でも `SPEC_INPUT_LINK_UNUSED` を必ず修正対象に含める。
    - **最終ガード**: リトライ後に残る場合は生成を失敗終了。

- **2026-03-17**: SPEC_INPUT_LINK_UNUSED の詳細情報を拡充
    - **変数名の付与**: 上流ノードの出力変数をメッセージに含めて原因特定を高速化。
    - **意図/エンティティの付与**: 対象ノードの `intent` と `target_entity` を併記。

- **2026-03-17**: ReasonAnalyzer で input_link 不整合の詳細を引き継ぎ
    - **パッチ情報の拡充**: `input_link`, `intent`, `target_entity`, `upstream_vars` を修正ヒントに付与。

- **2026-03-17**: Replanner で upstream_vars を再バインドに反映
    - **preferred_vars の注入**: `FIX_LOGIC_GAPS` で `preferred_vars` をノードに付与。
    - **SemanticBinder 優先解決**: `preferred_vars` をソース変数解決の最優先に設定。

- **2026-03-17**: input_link 使用検査の回帰テストを追加
    - **SpecAuditor 検証**: `SPEC_INPUT_LINK_UNUSED` が出ないことをユニットテストで確認。

- **2026-03-17**: SPEC_INPUT_LINK_UNUSED に修正推奨を追加
    - **推奨変数の提示**: 上流出力から `RECOMMEND=use:<var>` を付与し、リプランの精度を向上。
    - **ReasonAnalyzer 連携**: 推奨変数をパッチに渡し、`preferred_vars` に反映。

- **2026-03-17**: 推奨変数パッチの回帰テストを追加
    - **ReasonAnalyzer/IRPatcher 連携**: `RECOMMEND=use` が `preferred_vars` に反映されることを検証。

- **2026-03-17**: input_link 消失ポイントの推定を追加
    - **DROP_AT ヒント**: 変数の最終使用ノードを `DROP_AT=` として出力し、原因特定を高速化。
    - **ReasonAnalyzer 連携**: `drop_at` をパッチ情報として引き継ぎ。

- **2026-03-17**: DROP_AT を input_link 再接続に反映
    - **IRPatcher 連携**: `drop_at` が指定された場合、対象ノードの `input_link` を差し替え。

- **2026-03-17**: DROP_AT 再接続の回帰テストを追加
    - **IRPatcher 検証**: `DROP_AT` 指定時に `input_link` が差し替わることを確認。

- **2026-03-17**: input_link 消失の実例シナリオを追加
    - **InputLinkDropRepro**: `SPEC_INPUT_LINK_UNUSED` と `DROP_AT` の検出を再現可能にする設計書を追加。

- **2026-03-17**: SPEC_INPUT_LINK_UNUSED の誤検出抑制
    - **下流使用の考慮**: 下流ノードが上流変数を使用している場合は未使用判定を回避。

- **2026-03-17**: 未使用 POCO の出力抑制
    - **POCO生成の最小化**: 参照されないエンティティクラスは `BlueprintAssembler` で出力しないように修正。

- **2026-03-17**: FetchProductInventory の仕様整合と重複クエリ解消
    - **設計書修正**: Inventory を取得・表示する意図に合わせて `.design.md` を更新。
    - **生成コード修正**: 重複 SQL 実行と未使用変数を解消。

- **2026-03-17**: AggregationSummary の集計出力を修正
    - **集計値の型伝搬**: 合計値を `decimal` として追跡し、表示に正しく反映。

- **2026-03-17**: ドキュメント品質の向上と設計カバレッジの強化 (Documentation Coverage)
    - **主要モジュールの設計書完備**: `code_synthesis`, `pipeline_core`, `planner`, `replanner`, `design_parser`, `utils`, `code_verification` の主要コンポーネント 17 ファイルについて、詳細な設計書 (`.design.md`) を作成。
    - **アーキテクチャの可視化**: 各モジュールの Inputs, Outputs, Core Logic, Test Cases を厳密に定義し、実装と設計の乖離を防ぐ基盤を確立。
    - **自己修復・検証プロセスの明確化**: `IRPatcher`, `ReasonAnalyzer`, `SpecAuditor`, `SemanticAssertions` などの高度な検証・修復ロジックの仕様をドキュメント化。
    - **Design-to-Code プロセスの透明化**: `ActionSynthesizer`, `SemanticBinder`, `BlueprintAssembler`, `StatementBuilder` の役割分担とデータフローを明文化。

- **2026-03-11**: Phase 27 セマンティック解像度の精度向上
    - **アブダクション推論 (Abduction Inference) の実装**: `SemanticBinder` に型情報と計算目的からプロパティを逆引きする推論ロジックを導入。「価格」から `Price`、「種別」から `CustomerType` への高精度マッピングを実現。
    - **ビジネス計算 (CALC) 合成の安定化**: `ActionSynthesizer` の代入先特定アルゴリズムを強化。`10%割引` 等の指示から `item.Discount = item.Price * 0.9m;` のような代入式を安定生成。
    - **計算抽出ロジックの高度化**: `LogicAuditor` に複合名詞（ユーザー種別等）の変数ヒント抽出および、パーセント割引（Percent_Discount）の優先判定ロジックを追加。
    - **ビジネス類義語辞書の拡充**: `domain_dictionary.json` にプロジェクト固有の用語マッピング（種別 -> Type, Rank等）を追加。
    - **IR 生成の忠実度向上**: `IRGenerator` が構造化設計書の `target_entity` メタデータを優先的に尊重するよう改善。

- **2026-03-11**: Phase 25 実用的深度の向上と知識駆動型改善
    - **引数の意味的制約 (Semantic Constraints) の導入**: `SemanticBinder` に `literal_only`, `variable_only`, `no_null` 制約を実装。SQL パラメータへの変数誤バインドや mandatory 引数への `null` 注入を論理的に排除。
    - **定石パターンの拡充**: `action_patterns.json` に `pattern.dapper_query_single` および `pattern.http_post_json` を追加。HTTP POST 時の `StringContent` 自動構成に対応。
    - **エンティティ・モデルの一貫性 (Consistency) 強化**: `StructuralMemory` と `ASTAnalyzer` を拡張し、プロジェクト内の既存 `.cs` ファイルから POCO 定義（プロパティ）を自動抽出・インデックス化。合成時に既存定義を最優先で再利用する仕組みを実装。
    - **IR 生成層の精密化**: `IRGenerator` に引用符リテラルの自動抽出（URL, Path, SQL 等の判別）を追加。`StructuredDesignParser` の箇条書きマーカー処理を改善。
    - **合成エンジンの堅牢化**: `StatementBuilder` に C# 予約語の回避ロジック（`string` 変数名の防止等）および `is_constructor` メタデータへの対応を追加。

- **2026-03-10**: Phase 24 最終調整とロジック合成能力の極限強化
    - **Logic Survival Auditing の統合**: `CodeSynthesizer` に生成コードと IR ノードのロジック目標を照合する検閲ステップを追加。
    - **高度な LINQ / 計算式の合成**: `SemanticBinder` を拡張し、複数条件（AND/OR）、ラムダ式、および `(a + b) * c` 形式の構造化計算式の組み立てに対応。
    - **HTN パターン展開の実装**: `ActionSynthesizer` に `_process_htn_plan` を追加し、JSON 定義された複雑なロジックパターンの E2E 合成に対応。
    - **E2E 成功指標の達成**: 既存 7 シナリオに加え、新たに 3 シナリオ（SecureOrderProcessing, DailyInventorySync, UserReportGenerator）を定義し、計 10 件の E2E 合成・検証に成功。
    - **設計忠実度の向上**: `IRGenerator` が `data_source` などの設計書メタデータを直接解釈するよう修正し、ヒューリスティックによる誤判定を排除。
    - **Replanner の精度向上**: `BlueprintAssembler` で生成コードに Node ID コメントを埋め込み、`ReasonAnalyzer` がコンパイルエラー（CSxxxx）から修正対象の IR ノードを正確に特定可能にした。
    - **SandboxProvisioner の実装**: 検証用の隔離された C# 環境を動的に構築する機能を `CompilationVerifier` と統合。
    - **インテント判定の決定論的強化**: `SynthesisIntentDetector` に比較演算や入出力に関する決定論的キーワードを拡充し、ベクトル検索の揺らぎを抑制。

- **2026-03-06**: Phase 5 品質向上と全シナリオの完全自動合成の達成
    - **コンストラクタ自動生成の実装**: `CodeBuilder` (C#) を拡張し、`IDbConnection` や `HttpClient` などのフィールドを初期化するためのパラメータ付きコンストラクタを自動生成するロジックを導入。初期化漏れによる実行時エラーを根絶。
    - **レジリエンス・インジェクション (Try-Catch 自動挿入)**: `CodeSynthesizer` に IO/ネットワーク処理 (`DATABASE_QUERY`, `HTTP_REQUEST`, `FILE_IO`, `FETCH`) を `try-catch` ブロックで自動的にラップする機能を実装。例外発生時の安全なフォールバック（エラーログ出力）を標準化。
    - **高度な変数ホイスト (Hoisting) ロジック**: `try` ブロック内で宣言された変数が後続の処理で利用できるよう、スコープ外への宣言移動（ホイスト）とデフォルト値による初期化を自動化。データフローの整合性を維持しつつエラー耐性を向上。
    - **パラメータ・バインディングの精密化**: `_bind_parameters_advanced` に「アンチ・バインド規則」を導入。JSON 文字列をファイルパスに割り当てるような、型が同じでも意味が異なる誤バインドを完全に排除。また、POCO プロパティへのアクセス（`.Name` 等）やコレクションの集約操作（`string.Join`）の選択精度を大幅に改善。
    - **セマンティック検証のネスト対応**: `semantic_assertions.py` の `flatten_statements` を更新し、`try` ブロック内のメソッド呼び出しを再帰的に検出可能に。検証ゲートの精度を最新の合成エンジンに追従。
    - **全 7 シナリオの完全合成成功**: `FetchProductInventory`, `SyncExternalData`, `CalculateOrderDiscount` を含む標準 7 シナリオ全てにおいて、コンパイルエラーなし、TODO 残存なし、意味論的矛盾なしの高品質なコード生成を達成。

- **2026-03-06**: Design-to-Code パイプラインの強化と HTTP/JSON 連鎖の完成
    - **StructuredSpec 必須項目の強化 (Phase 1 拡張)**: `schemas/structured_spec.schema.json` を更新。`FETCH` および `DATABASE_QUERY` において `source_kind` および `source_ref` を必須化。`DATABASE_QUERY` では `semantic_roles.sql` を必須化し、設計段階での曖昧さを排除。
    - **Parser の欠損検出と Source Resolution の実装**: `StructuredDesignParser` に `validator.py` を統合し、パース時にスキーマ違反を 100% 検出する仕組みを導入。また、`data_sources` 定義から `steps` の `source_kind` を自動解決する Source Resolution 層の骨格を実装。
    - **HTTP/JSON 連鎖の完成 (Phase 4 接続)**: `HTTP_REQUEST -> JSON_DESERIALIZE` の定石パターンを、型制約付きで安定合成することに成功。`SyncExternalData` シナリオにおいて、`HttpClient.GetStringAsync` と `JsonSerializer.Deserialize<List<Product>>` の連鎖を完全自動生成。
    - **HTN Planner の検索精度向上**: `HTNPlanner` において定石パターン（`pattern.*`）の利用を解禁し、`source_kind` およびセマンティック・チェックによる厳格なメソッドフィルタリングを導入。`cancelpendingrequests` のような無関係なメソッドの誤認を大幅に低減。
    - **パターン展開 (Pattern Expansion) の再帰的サポート**: `CodeSynthesizer` を拡張し、HTN プラン内のステップがパターンである場合に、それを構成要素（メソッド呼び出し群）へ自動的に展開する機能を実装。
    - **エンティティ登録の柔軟性向上**: `_register_entity` を強化し、完全一致しないエンティティ名（例: Inventory）をキーワード検索により既存のスキーマ（例: Product）へ紐付けるフォールバックロジックを導入。
    - **決定論的構文解析の導入**: `IRGenerator` に二段階解析パイプラインを実装。制御構造（if/foreach/end）を、ベクトル判定の前に文法規則（助詞・接続助詞）で確定させることで、解析の安定性を劇的に向上。
    - **格フレーム解析（Semantic Linking）の実装**: 日本語の助詞（を、に、から）に基づき、引用符内の値が「パス」か「コンテンツ」か「SQL」かを構造的に特定するロジックを導入。生成層での正規表現依存を排除。
    - **MethodStore の Capability スキーマ導入**: 各メソッドに「何ができるか」を定義する `capabilities` フィールドを追加。ベクトル類似度のみに頼らない論理的なメソッドマッチングの基盤を構築。
    - **自動収集ツールの能力推論強化**: `MethodHarvesterCLI` (C#) および `MethodHarvester` (Python) をアップグレード。型情報や名前空間からメソッドの能力を自動推論するロジックを組み込み。
    - **既存データのアップグレード**: `scripts/upgrade_method_metadata.py` を実行し、既存の 1,157 個のメソッド全てに Capability メタデータを一括付与。
    - **論理抽出の厳格化**: `LogicAuditor` において、比較キーワードがない場合の安易なゴール生成を抑制し、意図判定のノイズを低減。
    - **バグ修正**: 計算数値の抽出漏れによる NoneType エラーや、トークン伝搬フローの不備による解析の早期終了問題を修正。

- **2026-03-04**: MethodStore の統合と SemanticSearchBase の基盤強化
    - **MethodStore の単一ソース化**: `resources/method_store_meta.json` を廃止し、`resources/method_store.json` を唯一の正解（Source of Truth）として統一。
    - **add_method の実装**: `MethodStore` に `add_method` を実装。`MethodHarvester` や `AutonomousSynthesizer` からの動的なメソッド追加に対応。
    - **永続化メカニズムの改善**: `MethodStore.save()` を実装し、追加されたメソッドを `resources/method_store.json` に書き戻すように変更。
    - **SemanticSearchBase の汎用化**:
        - `config` オブジェクトからのパス解決に対応。
        - ベクトルエンジンが未指定の場合でも、ゼロベクトルを使用してメタデータをロード・検索できるよう修正（ユニットテスト等の環境対応）。
        - `hybrid_search` にデフォルトのキーワードマッチングを実装し、ベクトルがない環境でも基本的な検索を可能にした。
        - スコアが 0 以下の結果をフィルタリングするよう改善。
    - **不整合なインポートの修正**: `scripts/manage_vector_db.py`, `scripts/run_harvest.py`, `tests/verification/test_poco_reverse_inference.py` 等の壊れたインポートパスを `src.code_synthesis` へ修正。
    - **ユニットテストの修復**: `tests/unit/test_method_store.py` を新アーキテクチャに合わせて修正し、全てのテストがパスすることを確認。

- **2026-02-26**: コード合成エンジンの現状課題に関する検証と報告書の更新。
    - **デモスクリプトによる実態調査**: `scripts/demo_synthesis.py` を実行し、生成された C# コードの論理的破綻（ファイル名とコンテンツの混同、無関係なメソッドの呼び出し、非同期代入の型不整合、制御ブロックの消失等）を詳細に分析。
    - **課題報告書の拡充**: `docs/code_synthesis_issues_report_20260226.md` に、新たに判明した「妄想的なメソッド呼び出し」「Await代入の不整合」「検証プロセスの形骸化」等の項目を追記。
    - **テスト資産の健全性確認**: 既存のユニットテストおよび `tests/repro_linq.py` 等を実行し、API仕様変更に伴う広範囲なテストの腐敗（Bit Rot）を確認。
    - **解決の方向性の再定義**: コンパイルエラーメッセージのフィードバックループ構築や、テストスイートの刷新を提案。
    - **中心化されたスコア管理**: `MethodStore` と `CodeSynthesizer` のハードコードされたマジックナンバーを排除。`base_scores`, `domain_bonuses`, `verb_priorities`, `deterministic_rules` を `scoring_rules.json` から動的に読み込むよう刷新。
    - **検索精度の再調整**: 正規化されたスコア環境下での重み付け（契約・意図・キーワード）を再設計し、LINQ や Dapper などの重要コンポーネントの選択安定性を向上。
    - **型不整合ペナルティの統合**: `TypeSystem` で定義された型不整合ペナルティをパラメータバインディングに適用。

- **2026-02-24**: Roslynベースの構造的合成エンジンへの完全移行。
    - **C# CodeBuilderツールの構築**: `tools/csharp/CodeBuilder` を新設。Roslyn (Microsoft.CodeAnalysis) を活用し、論理設計図（JSON）から文法的に100%正しく、整形された C# コードを生成する仕組みを実装。これにより文字列結合時代の構文エラーを根絶。
    - **Blueprint方式への移行**: `IREmitter` および `CodeSynthesizer` を刷新。文字列結合を廃止し、抽象的なステートメント構造を出力・統合する方式に転換。
    - **データフローの整合性強化**: グローバル・リテラル検索を実装。ネストされたブロック内でも最初のステップで提示されたファイル名（"config.json"等）を正確に参照・再利用可能に。
    - **意味論的バインドの精密化**: `path`, `sql`, `content` などのロール情報を厳格化。`bool` 型の結果を誤ってパス引数にバインドするような意味的矛盾を排除。
    - **非同期処理の自動対応**: `CodeBuilder` 側で `Task` を返すメソッドへの `await` 自動付与およびメソッドの `async` 化をサポート。
    - **高度なネスト合成の安定化**: `Retry` ブロック内に `File.ReadAllTextAsync` を埋め込むなどの、複雑な構造の合成に成功。

- **2026-02-24**: 構造的合成エンジンの進化と論理ネストの完全対応。
    - **Intent Fulfillment（意図の充足）による厳格化**: 合成エンジンにおいて、特定の意図（FILE_IO等）が指定された際にメソッドが見つからない場合、以前のようにステップをスキップせず、TODOを生成してパスのスコアを下げるように変更。これにより、不完全なコードが「成功」として選ばれる問題を根本解決。
    - **Domain Alignment Bonus（ドメイン一致ボーナス）**: インテント（FILE_IO, DATABASE_QUERY等）とクラス名（System.IO, Dapper等）が一致する場合にスコアを加算するロジックを導入。`Console.Read` と `File.ReadAllText` のような、動詞は同じだがレイヤーが異なるメソッドの誤認を防止。
    - **IRレベルでの構造ネスト実装**: `IRGenerator` を拡張し、`Retry` などのラッパーノードを構造的ノードとして扱うよう変更。後続のステップを自動的に `body` 内へネストする機能を実装。
    - **ラッパーメソッドの再帰的生成**: `IREmitter` に `_emit_retry` を実装し、ラムダ式（`Action`/`Func`）を伴う複雑な C# 構文の再帰的生成に対応。
    - **論理ブロックの自動クローズ**: 設計ステップの末尾において、保留中のブロック（`if`, `foreach`, `retry`）を自動的に閉じる補完ロジックを `IRGenerator` に追加。
    - **コンテキスト依存の論理式生成**: `_generate_logic_expression` において、直前のステップで生成された `bool` 変数（`File.Exists` 等の結果）を `if` 条件として優先的に再利用するパス追跡を実装。
    - **自律的修復ループの統合**: `CompilationVerifier` と `LogicAuditor` を合成プロセスにインラインで組み込み、エラー発生時の自動ペナルティ付与と再試行（Repair）を実現。
    - **日本語解析の抜本的修正**: `MethodStore` と `SymbolMatcher` への `MorphAnalyzer` 供給不足を解消し、日本語キーワードの識別精度を大幅に向上。

- **2026-02-20**: コード合成エンジンの最終品質向上 (Final Polish)。
    - **日本語プロパティマッピングの精密化**: `CALC` インテントにおいて「合計」「価格」などの日本語キーワードを `Total`, `Price` プロパティへ確実にマッピングするフォールバックを実装。
    - **引数バインディングの一意性確保**: 同一メソッド呼び出し内で同じ変数が重複してバインドされるのを抑制し、`Console.Write(json, total)` のような自然な引数割当を実現。
    - **シリアライズ条件の最適化**: `FILE_IO` における自動シリアライズ判定を改善し、フィルタリング後のコレクション保存ステップが消失する問題を解消。
    - **メソッド優先順位の調整**: `DISPLAY` インテントにおいて `WriteLine` を `Write` より優先するバイアスを追加。

    - **Global Entity Analysis (事前走査)**: 全ステップを事前に解析し、プログラム全体で支配的なエンティティ（例: `Order`）を特定。メソッド選択時にこのコンテキストを優先することで、エンティティの誤認を防止。
    - **Look-ahead Property Matching (先行要求チェック)**: メソッドの戻り値型を決定する際、後続ステップで必要となるプロパティ（例: `Total`, `CustomerType`）を保持している型を優先的に選択するロジックを実装。
    - **Composite Variable Naming (コンポジット命名法)**: 計算結果などの変数名において、元のプロパティ名と操作を組み合わせた名前（例: `total_discount`）を自動生成し、名前の衝突と意味の曖昧さを解消。
    - **自動シリアライズの最適化**: 冗長な `JsonSerializer.Serialize` の生成を抑制し、必要なコンテキスト（ファイル出力、明示的指示）でのみ適用されるようロジックを精緻化。
    - **ドメインガードの強化**: プロパティ名のみの一致による誤判定を抑制し、クラス名・メソッド名に基づく意味的なマッチングを最優先化。
    - **Scenario 7 の完全自動合成**: 複雑な条件分岐、計算、リポジトリ経由のデータ取得を含む高度なビジネスロジックの合成に成功。

    - **コレクション表示の適正化**: `IEnumerable` 等のコレクションを直接 `WriteLine` するのではなく、`foreach` によるプロパティ展開または `JsonSerializer` によるシリアル化を自動選択するよう改善。
    - **変数スコープの自動ホイスティング強化**: 複数の `if/else` 分岐で宣言された同名変数を検出し、ブロック外へ宣言を移動（ホイスティング）することでスコープエラーを完全に解消。
    - **文脈依存の `else` ブロックメッセージ**: `else` ブロック内でのエラー表示において、直前の `File.Exists` 等の条件を解析し、「config.json not found」のような具体的なエラー文を自動生成。
    - **ロジカル・フィルタリングの導入**: スコアのインフレに頼らず、後続ノード（`LOOP`等）の要求型に基づいたメソッド選択や、インテントとクラスの厳格な一致判定（Hard Filter）を実装。
    - **JSONインフラメソッドの排除**: `MakeReadOnly` や `Utf8JsonWriter` の低レイヤーメソッドが、高レイヤーな `Deserialize` よりも優先される問題をブラックリスト化により解決。
    - **条件式生成の高度化**: 「金額が5000より大きく、かつ顧客タイプがPremium」といった複合的な日本語指示から、型推論を交えた正確な C# 論理式（`item.Total > 5000m && item.CustomerType == "Premium"`）を抽出可能に。
    - **コントロールフローのパス分離修正**: `IREmitter` において、`if` ブロックの最終状態が `else` ブロックに混入するバグを修正し、各分岐が正しい変数コンテキストで開始されるよう改善。

    - **過剰なシリアライズの抑制**: 指示文に「JSON」「シリアライズ」等の明示的な指定がない限り、自動的な `JsonSerializer.Serialize` の追加を原則廃止。
    - **プロパティアクセスの最優先化**: 「アイテムの名前」等の指定がある場合、オブジェクト全体ではなく `item.Name` 等のプロパティアクセスを優先的に生成するよう改善。
    - **リテラルの大文字/小文字保持**: 論理式生成において、比較対象のリテラル（"A" 等）が小文字化される問題を修正。
    - **ジェネリクス具象化の精密化**: `T Deserialize<T>` のような型引数が戻り値そのものである場合と、`IEnumerable<T> Query<T>` のようなラップされた場合を判別し、`List<Product>` 等の適切な型を導出。
    - **HTTP/JSON リンケージの改善**: HTTP 取得結果のロールを自動的に `content` に設定し、後続のデシリアライズ処理へのバインド精度を向上。
    - **デフォルト SQL 生成の導入**: `DATABASE_QUERY` インテントで SQL が未指定の場合、ターゲットエンティティから `SELECT * FROM Orders` 等のクエリを自動補完。
    - **条件分岐の変数バインディング修正**: ループ内での `if` 条件式において、コレクション変数ではなくループ変数（`item`）を優先的に参照するよう改善。
    - **DISPLAY フォールバックの強化**: 表示対象が見つからない場合、意味のない `ToString()` ではなく、文脈に応じたデフォルトメッセージ（"Operation failed." 等）を出力。
    - **スコアの正規化**: 全モジュールのスコアリングを 0-20 の範囲に再調整し、意図的なインフレを排除（Conventions 準拠）。
    - **ロール定義の完全修復**: `sync_method_store.py` において、`Query`, `Execute`, `WriteLine` 等の主要メソッドに欠落していた `role` を追加。Dapper の引数割当精度が劇的に向上。
    - **POCO 生成の復元**: 消失していたエンティティクラス（`User`, `Product` 等）の自動定義機能を再実装。
    - **ジェネリクス推論の同期**: 変数型とメソッドの型引数（`Query<Product>` 等）が一致するよう推論ロジックを修正。
    - **フォールバック検索の強化**: インテントに依存せず、キーワード（「リトライ」等）に基づいて共通ユーティリティを抽出可能に。
    - **変数ホイスティングの一般化**: 全ブロックを対象に変数の宣言位置を自動調整し、スコープエラーを根絶。

    - **メソッド呼び出しの完全正規化**: 静的メソッド（`Console.WriteLine` 等）のクラス名欠落を修正し、`receiver` 生成ロジックを厳格化。
    - **拡張メソッドの正確な処理**: Dapper の `Query` 等の拡張メソッドにおいて、`this` パラメータを引数リストから正しく除外。
    - **条件分岐の変数バインディング改善**: `File.Exists` 等の戻り値を `if` 文の条件式として直接利用するロジックを実装。
    - **ループソースの動的解決**: `input_link` を活用し、`foreach` 文が直前のステップで生成されたコレクション変数を正確に参照するよう改善。
    - **CALC インテントの導入**: 「15%として計算」といった指示から算術演算式（`* 0.15m`）を直接合成する機能を実装。
    - **セマンティック・サチュレーションの精密化**: ターゲット型が既に存在する場合にのみ冗長な変換をスキップするよう判定を厳密化。
    - **サービス束縛のガード**: リポジトリや接続オブジェクトが、意図しない一般引数として渡されるのを防止。

    - **厳格なセマンティック・ロール束縛 (Phase 1)**: `sql`, `url`, `path` といった特定のロールを持つ引数に対し、型の一致だけでなくロールの一致を強制。`item.ToString()` が SQL 引数に渡されるなどの論理矛盾を根絶。
    - **命名規則の正規化 (Phase 2)**: C# 命名規約に従い、`IDbConnection` -> `_dbConnection` のような camelCase フィールド名の生成を実装。
    - **ドメインガードの強化 (Phase 3)**: `MethodStore` にドメイン辞書を統合し、指示文内の名詞（「商品」「在庫」等）とメソッドのドメイン不一致を強力にペナルティ化。
    - **論理式生成と構造の改善 (Phase 4)**: 
        - `IRGenerator` を刷新し、ループや条件分岐のネスト構造を正確に抽出。
        - `LINQ` インテント専用の処理を追加し、`Where` 句の正確な合成を実現。
        - 複雑なオブジェクトの「自動シリアル化」タイミングを最適化し、LINQ 操作後の display/io 時にのみ適用されるよう改善。
    - **型システムの精密化**: `ToString()` の優先度を大幅に下げ、他に適合する変数が存在しない場合の最終手段としてのみ機能するように調整。
    - **デモシナリオの品質向上**: シナリオ 1 (ProcessActiveUsers) で、全ステップ（取得・絞り込み・シリアル化・保存）が論理的整合性を保って合成されることを実証。

    - **プロパティ抽出の優先化**: LINQ および条件分岐において、単なる存在チェックをバイパスし、指示文内の述語に基づいたプロパティ操作（`item.Price > 100` 等）の抽出を最優先化。
    - **ハード・インテント・フィルタ**: `EXISTS`, `DISPLAY`, `LINQ` 等の特定のインテントに対し、戻り値の型不一致なメソッドを検索段階で厳格に除外。
    - **厳格なリテラル・ロール束縛**: パス (`path`) や URL (`url`) リテラルが、部品側の無関係な引数に誤ってバインドされるのを防止。
    - **高度なエンティティ推論**: ループ内のコレクション型から要素型（`IEnumerable<Order>` -> `Order`）を自動抽出し、ブロック内でのプロパティ参照コンテキストを自動復元。
    - **日本語オペレータ対応の拡充**: 「大きく」「小さく」「超える」「未満」といった多様な表現から比較演算子へのマッピング精度を向上。
    - **シナリオ 1, 2, 6, 7 の完全復元**: 複雑な条件分岐、Dapper による SQL 実行、高度な LINQ 合成の整合性を実証。

- **2026-02-18**: `CodeSynthesizer` および `IRGenerator` の意味的正確性をさらに強化。
    - **セマンティック・サチュレーション (Chain Control)**: 複合メソッド（FetchAndParse等）実行後に冗長な変換ステップをスキップする「意味的飽和」ロジックを実装。
    - **インテント優先順位の最適化**: `DISPLAY` インテントがループ内や複雑な文脈で他のインテントに上書きされる問題を修正。
    - **EXISTS インテントの導入**: ファイル存在チェック等の真偽値操作を独立したインテントとして定義し、後続の条件分岐へのリンケージを自動化。
    - **型システムのブリッジ強化**: `IEnumerable` -> `string` 等の暗黙的変換において `JsonSerializer.Serialize` 等のテンプレートを強制適用するよう改善。
    - **ジェネリクス具象化の改善**: コンテキストヒント（「リスト」「一覧」等）から `List<T>` への自動ラップに対応。
    - 日本語の助詞（「が」「を」「の」「より」等）に基づく依存構造木（`syntax_tree`）の生成に対応。
    - 後方互換性（`analysis.chunks`）を維持し、既存パイプラインへの影響をゼロに。
- **2026-02-17**: `CodeSynthesizer` の妥当性とビルド可能性を強化。
    - **変数ホイスティング**: `if/else` 内の宣言をメソッド冒頭に移動し、スコープエラーを根絶。
    - **決定論的バインド**: SQLリテラルのバインド精度向上と比較演算子のパース改善。
    - **エンティティ解決の堅牢化**: 名前空間セグメントの誤認防止とスキーマからの直接プロパティ復元を実装。
- **2026-02-17**: `CodeSynthesizer` 意味理解・論理合成エンジンの抜本的強化。
    - **セマンティック・ガードレール**: `role` (`url`, `path`, `content`) に基づく厳格な引数バインドを実装し、意味的な引数混同を根絶。
    - **充足率スコアリング**: 指示文内の全リテラルの使用を強制するロジックを導入し、指示の読み飛ばしを防止。
    - **LINQインテントの昇格**: インテントに応じたメソッド選択ロジックを強化し、`Where` ラムダ式の正確な生成（`x => x.Price > 100m` 等）を実現。
    - **高度なシンボルマッチング**: `SymbolMatcher` に `VectorEngine` を統合し、自然言語とコードシンボルの意味的類似度判定を高度化。
    - **コンテキスト維持**: ステップ間でのエンティティ情報（`main_poco`）の伝搬と、ジェネリクス型の具象化（`IEnumerable<Order>` 等）を改善。
    - Updated `MethodHarvesterCLI` (C#) and `MethodHarvester` (Python) to automatically infer parameter roles (`url`, `path`, `content`, etc.) based on naming and context.
    - Enhanced `CodeSynthesizer` with "Literal Locality" to prevent cross-step literal bleeding.
    - Implemented role-based binding strictness (e.g., `url` role requires `http` prefix).
    - Strengthened Domain Class Enforcement to prioritize methods from classes mentioned in instructions.
    - Refined beam search fallback logic to maintain path viability using TODO comments without immediate score collapse.
- **2026-02-17**: Improved synthesis chaining with Ghost Variables and Scoring Overhaul.
    - Implemented "Ghost Variables" to allow synthesis to continue even if a step fails, by registering placeholder variables with inferred types.
    - Refactored `_process_action_node` to handle synthesis failures gracefully without breaking the beam search.
    - Adjusted scoring rules to prioritize completion rate and specific keyword matches.
    - Updated `FetchAndParseJsonAsync` to Tier 3 (Deprecated) to favor atomic `ApiClient` methods.
- **2026-02-17**: Refined Intent inference and added TODO fallbacks.
    - Implemented `// TODO` fallback in `IREmitter` and `CodeSynthesizer` to allow synthesis to continue even when steps are missing.
    - Expanded `JSON` intent keywords to include retrieval verbs ("取得", "fetch") to prevent filtering of network methods.
    - Increased beam width to 10 and adjusted keyword bonuses to improve recall.
    - Added loop context property priority to improve variable binding inside loops.
- **2026-02-17**: Normalized scoring and ensured Harvester compatibility.
    - Normalized `CodeSynthesizer` and `MethodStore` scoring rules to prevent inflation (using 0-20 range instead of 500+).
    - Updated `MethodStore.add_method` to preserve existing `tier` information when updating from external tools like Harvester.
    - Fixed build error in Scenario 2 by implementing `IEnumerable` detection and automatic `JsonSerializer.Serialize` wrapping for `System.Console` methods.
    - Improved `WriteLine` prioritization for display-related intents.
- **2026-02-17**: Implemented Strict Data Chaining and Deep Contextual Memory.
    - Introduced `require_link` flag in IR nodes to enforce strict argument binding in `CodeSynthesizer`.
    - Refactored `CodeSynthesizer` and `IREmitter` to support "Deep Contextual Memory" by extracting all literals at start and synchronizing memory across branches.
    - Added "Recommendation Tier" metadata support to `MethodStore` to prioritize high-layer standard APIs.
    - Enhanced plurality strictness for `IEnumerable` types and improved parameter name matching scoring.
    - Fixed `if/else` sequencing bug in `IREmitter` to ensure both branches are correctly emitted.
    - Prevented no-op `if (true)` generation by adding `// TODO: Condition Unknown` fallbacks.
- **2026-02-16**: Integrated Arithmetic Expression support and Critical Intent prioritization.
    - Added `CALC` node type to IR for direct C# arithmetic generation (percentages, etc.).
    - Implemented "Critical Intent Bonus" to ensure DB/HTTP operations are prioritized over unrelated methods.
    - Enhanced variable hoisting and prioritized recently calculated results (e.g., `amount`) in parameter binding.
    - Improved data flow integrity across nested blocks.
- **2026-02-16**: Enhanced Data Flow integrity and Parameter Binding logic.
    - Implemented "Hallucination Penalty" to prevent the use of undefined variables.
    - Refactored `TypeSystem` to prioritize direct property access and `ToString()` over collection-wide serialization.
    - Added Context-Aware Scoring (Loop Item Priority) to ensure correct variable selection inside blocks.
    - Improved Property Matching using `MorphAnalyzer` and keyword-based prioritization.
- **2026-02-16**: Established full `NLP -> IR -> C#` synthesis pipeline.
    - Integrated `IRGenerator`, `IRValidator`, and `IREmitter` into `CodeSynthesizer`.
    - Implemented recursive tree-based emission with beam search state preservation.
    - Enhanced method scoring with async-context awareness and parameter connectivity bonuses.
    - Improved Japanese intent inference and cross-node literal inheritance.
- **2026-02-13**: Enhanced synthesis reliability and IR readiness.
    - Implemented `IRGenerator` to create structured logical trees from natural language.
    - Restored and optimized beam search in `CodeSynthesizer` to maintain high synthesis quality while being IR-ready.
    - Improved Japanese keyword matching for entity detection and logic generation.
    - Fixed type system hallucinations by normalizing bridge conversion scores.
    - Verified all demo scenarios, achieving high-quality LINQ and structural logic generation.

- **2026-02-12**:
    - **コード合成の論理バインディングと型システムの強化**:
        - `TypeSystem` に数値の暗黙的型変換（Widening Conversion: int -> long 等）を導入。
        - ジェネリクス推論 (`Query<T>`, `Deserialize<T>`) を改善し、文脈から POCO クラス名を特定する精度を向上。
        - 変数のスコープ問題を修正（`try` ブロック外での変数宣言）し、ビルドエラーを抑制。
        - プロパティのない POCO クラスでも、コード内で使用されている場合は生成するように変更。
    - **外部エコシステム（NuGet）連携の自動化**:
        - `DynamicHarvester` に `harvest_from_package` を実装し、`MethodHarvesterCLI` による NuGet DLL からのメソッド抽出を実現。
        - `NuGetClient` を拡張し、ローカルキャッシュから最適なターゲットフレームワークの DLL を自動選択する機能を追加。
    - **修復サイクルの高速化と検証の統合**:
        - `scripts/demo_synthesis.py` に `CompilationVerifier` を統合。生成直後にビルド可能性を検証し、結果をフィードバックする仕組みを構築。
        - 検証時の NuGet 依存関係を自動解決し、プロジェクトファイル (`.csproj`) を動的に更新するロジックを実装。

- **2026-02-12**:
    - **コード合成の構文・構造品質の向上**:
        - `_finalize_code` におけるインデント再計算ロジックを刷新し、ネスト深さに応じた正確なフォーマット出力を実現。
        - POCO クラスの重複生成を完全に排除し、プロパティのない空クラスの生成を抑制。
        - `if` 条件式における bool 変数の紐付け精度を向上。
        - 解決不能な `{target}` プレースホルダを TODO コメント化し、構文エラーを防止。
    - **メソッドストアの汎用性向上とSQL対応**:
        - `MethodStore` に SQL 操作 (Dapper形式)、高度な LINQ、レジリエンスパターンのテンプレートを追加。
        - パラメータに `role` (target, path, input 等) を導入し、コード合成時の引数バインディング精度を向上。
    - **管理スクリプトの完全一本化と堅牢化**:
        - `scripts/sync_method_store.py` を自己完結型にリファクタリング。
        - プロジェクトスキャン、システムメソッド登録、ベクトルDB同期を一つのコマンドで完結。
        - 以前の冗長なシードスクリプト群を完全に整理。
    - **テストスイートの整理と信頼性向上**:
        - 失敗していた19件のユニットテストをすべて修正。
        - `CodeSynthesizer` テストの完全モック化により、実環境データの汚染を防止。
        - `SafetyPolicyValidator` の判定を強化し、安全性を向上。
        - 不要なテストの削除と、テスト意図を明確にするためのリネームを実施。
    - **設定管理の統合 (TaskManagerConfig の廃止)**:
        - `src/task_manager/config.py` を廃止し、`ConfigManager` に設定を集約。

- **2026-02-10**:
    - **Pipeline Stage パターンの導入**:
        - `Pipeline.run` を `Stage` 抽象クラスに基づく 8 つの独立した工程に分割。
    - **セマンティック・フィードバックの強化**:
        - `FailureAnalyzer` に `semantic_mismatch` 判定を導入。
    - **ログの自動ローテーションとアーカイブ**:
        - `scripts/rotate_logs.py` を作成。
    - **ユーザー嗜好（Coding Style）の反映**:
        - `config/user_preferences.json` を新設。
    - **C# 深層依存関係解決の強化**:
        - `DependencyResolver` を拡張。
    - **パス操作の標準化**:
        - `src/utils/context_utils.py` に `normalize_path` を追加。
- **2026-03-19**:
    - **ActionSynthesizer の正規表現依存を低減**:
        - 集計ヒントの数値判定、表示メッセージの引用抽出、`Task<T>` アンラップ、ジェネリック内側型抽出を簡易パーサに置換。
        - `JSON_DESERIALIZE` と LINQ 系の型抽出で同一ヘルパを使用し、挙動の一貫性を向上。
        - 単語境界チェックと SQL パラメータ抽出を簡易パーサ化し、regex を排除。
    - **SemanticBinder の正規表現依存を低減**:
        - URL 抽出、SQL パラメータ抽出、数値/識別子判定、%/小数抽出を簡易パーサ化。
    - **IRGenerator の正規表現依存を低減**:
        - URL/SQL/引用リテラル/数値抽出とジェネリック内側型抽出を簡易パーサ化。
        - TRANSFORM/PERSIST で content を roles に明示し、input_link がある場合は強制を回避。
    - **ActionSynthesizer が解析結果を優先利用**:
        - `semantic_roles` の `content/message/notification` を表示処理で優先し、キーワード依存を抑制。
        - DISPLAY の引用抽出フォールバックを削除し、roles 優先化を強化。
        - 通知フォールバックを roles 未設定時のみに限定し、フォールバック依存を縮小。
        - CALC で `semantic_roles` の `target_hint` / `property` / `quantity_prop` を優先し、推測分岐を縮小。
        - TRANSFORM/PERSIST 関連の roles 取得を統一し、フォールバックの前段を解析結果に寄せた。
- **2026-04-13**: Documented security policy, unified command allow-lists under config safety policy, added disallowed options and stricter approvals (including pipeline confirmation and script --confirm), stabilized security tests, documented allow-unsafe usage rules across scripts and security policy, defined the approval flow state transitions, restricted python/py execution to scripts/ allowlist only (with update guidance), added keyword-based log masking, restricted read/list commands to configured directories, narrowed read_allowed_dirs to a minimal set, added token-based read_blocked_rules (with update guidance), enforced backups for high-risk changes, clarified allowlist normalization rules, defined absolute prohibitions, documented backup retention, added backup pruning script, and documented dry-run/CI usage.
- **2026-04-14**: Added `npm` to safe commands and aligned the default read-allowed directories to the minimal policy set (`AIFiles/config/docs/scripts/src/tests`).
- **2026-04-30**:
    - **IR meaning preservation の `CHECK` 系を強化**:
        - `IRGenerator` が `spec_role=CHECK` の条件ノードで `intent=EXISTS`, `role=CHECK`, `check_kind`, `check_subject`, `expected_truth` を保持するよう改善。
        - `null_check` では識別子 subject を保持し、`comparison_check` では比較演算子と比較値を保持。
        - `ActionSynthesizer` / `SemanticBinder` が `spec_role` と `check_kind` を参照し、`DESERIALIZE`, `FILTER`, `CHECK` を runtime 側で消費できるよう改善。
        - `comparison_check` は `target_entity=Item` のままでも既知 POCO から property を逆引きし、loop 文脈付き条件式を生成できるよう改善。
    - **IR 研究文書と観測ログを同期**:
        - `research/ir_meaning_preservation/` 配下の `CHECK` ベンチマーク観測結果、ケース差分、保存済み `observed_ir` を最新実装に合わせて更新。
    - **外部レビュー提案を研究計画へ反映**:
        - `Dependency Loss` の edge-focused 分析、明示チェーン vs 自動チェーン比較、`LOOP` / `WRAPPER` の構造境界評価、否定系 `CHECK` 比較を次段研究課題として明記。
    - **Dependency Loss を独立分析として追加**:
        - `dependency_loss_analysis.md` を作成し、依存損失を `Edge Break`, `Edge Misbinding`, `Compression-Induced Loss`, `Boundary Drift` の 4 型で整理。
        - `RobustConfigLoader`, `BatchProcessProducts`, `SyncExternalData`, `ComplexLinqSearch` を使って、構造跨ぎ誤接続と前段圧縮を role drift から切り離して記述。
    - **Dependency Loss の実装トレースを追加**:
        - `dependency_loss_trace.md` を作成し、`RobustConfigLoader` の `else_children.input_link = step_3` が、`ELSE` で配置先だけ切り替えつつ `last_node_id` を then 側のまま持ち越すことで発生していると整理。
    - **ELSE 分岐の依存誤接続を修正**:
        - `IRGenerator` の `block_stack` に branch base を持たせ、else 側最初のノードが then 側の `last_node_id` ではなく対応 `CONDITION` ノードへ接続されるよう改善。
        - `test_else_children_input_link_uses_condition_branch_base` を追加し、`RobustConfigLoader` 型の `else_children.input_link` が条件ノードへ戻ることを固定。
    - **構造親優先の依存規則を LOOP / WRAPPER に一般化**:
        - 構造ブロック内の最初の子ノードは、直前ノードではなく構造親の branch base を既定 `input_link` とするよう調整。
        - `test_generate_nested_structure` で wrapper 直下と loop 直下の first-child 接続を固定。
    - **構造親依存規則を研究文書として固定**:
        - `structural_dependency_rule.md` を追加し、`CONDITION`, `LOOP`, `WRAPPER` に共通する `structural_parent_dependency` と `sequential_sibling_dependency` を定義。
        - `evaluation.md` に「構造親依存と sibling 依存の区別」を評価観点として追記。
    - **構造親依存規則の補助ベンチマークを追加**:
        - `case_09_condition_branch_dependency.md`, `case_10_loop_body_dependency.md`, `case_11_wrapper_scope_dependency.md` を追加。
        - `CONDITION`, `LOOP`, `WRAPPER` それぞれについて `first-child`, `second sibling`, `nested child` を比較できるように整理。
    - **構造親依存ケースの期待 IR を具体化**:
        - `case_09` から `case_11` について、`structural_parent_dependency` と `sequential_sibling_dependency` を読み分けられる `Expected IR` を追加。
    - **構造親依存ケースの初回観測を追加**:
        - `case_09` から `case_11` の `Observed IR` を保存し、`structural_dependency_observation.md` で比較結果を要約。
        - `CONDITION` では branch dependency が期待どおり成立し、`LOOP` では second sibling が collection 優先規則に上書きされることを確認。
    - **構造ブロック内部で sibling 依存を優先するよう調整**:
        - `IRGenerator` の `input_link` 決定で、構造ブロック内に既存 sibling がある場合は `branch_last_id` を `last_collection_id` より優先するよう改善。
        - `case_10_loop_body_dependency` で `step_4.input_link` が `step_2` ではなく `step_3` になることを確認。
    - **構造 role の橋渡し方針を整理**:
        - `IRGenerator` が retry wrapper に `spec_role=WRAP`、loop 構造に `role=ITERATE` / `spec_role=ITERATE` を付与するよう改善。
        - `structural_role_bridge.md` を追加し、`CALCULATE` は runtime role へ橋渡し、`ITERATE` は node type 主体、`WRAP` は保存優先とする方針を整理。
    - **CALCULATE の弱化を局所分析**:
        - `calculate_role_analysis.md` を追加し、`価格を計算する` のようなケースが `logic_goals` 不足により `GENERAL/ACTION` へ落ちることを整理。
        - `CALCULATE` は downstream bridge より upstream detection が主課題であると明記。
    - **CALCULATE 補助ベンチマークを追加**:
        - `case_12_calculate_with_target_hint.md` と `case_13_calculate_without_target_hint.md` を追加。
        - explicit target hint あり/なしで `CALCULATE` 検出安定性を比較できるよう整理。
    - **CALCULATE 補助ケースの期待 IR を具体化**:
        - `case_12` と `case_13` に `CALC/CALCULATE` を期待する基準形を追加し、target hint あり/なしで差分比較できる状態にした。
    - **CALCULATE 補助ケースの初回観測を追加**:
        - `case_12` と `case_13` の `Observed IR` を保存し、`calculate_case_observation.md` で比較結果を要約。
        - target hint を付けても現状は `GENERAL/ACTION` から `CALC/CALCULATE` へ昇格しないことを確認。
    - **CALCULATE 昇格規則を設計**:
        - `calculate_promotion_rule.md` を追加し、`logic_goals.calculation` または `target_hint/property + calculation intent` の組み合わせでのみ `CALCULATE` へ上げる最小規則を定義。
        - 単語だけ・metadata だけでは昇格させない方針と、`case_12` / `case_13` を使った受け入れ条件を明記。
    - **CALCULATE 昇格規則を実装**:
        - `IRGenerator` に `target_hint/property + calculation intent` による最小昇格規則を追加し、`case_12` は `CALC/CALCULATE`、`case_13` は `GENERAL/ACTION` のまま残ることを確認。
        - `test_calculate_promotes_with_target_hint_and_calculation_intent` と `test_calculate_does_not_promote_without_target_hint` を追加。
## 2026-05-01

- Added provenance-strength boundary benchmark definitions for `CHECK` and `FILTER` in `case_18_check_provenance_strength_boundary.md` and `case_19_filter_provenance_strength_boundary.md`, along with benchmark index updates to support exact-scope validation.
- Added `research/ir_meaning_preservation/provenance_strength_policy_matrix.md` to formalize a cross-role provenance-strength matrix for `CHECK`, `FILTER`, and `CALCULATE`, including exact-scope rules and allowed/forbidden downstream concretization.
- Updated `research/ir_meaning_preservation/README.md` and `document_map.md` to register the new provenance-strength policy document in the foundation set.

- **2026-05-01**: Performed a final consistency pass across synthesis and alias-admission documents, fixing stale next-step references and the thesis-claim count in midterm_synthesis.md.
- **2026-05-12**:
    - **TRANSFORM provenance を deterministic metadata として固定**:
        - `src/ir_generator/transform_resolution.py` を追加し、`ops` がある場合の `transform_op_resolution=explicit_ops`、explicit `source_var`、structural upstream source に対する `transform_source_resolution` / `transform_source_node_id` を供給するよう改善。
        - `IRGenerator` は `spec_role=TRANSFORM` に対して provenance metadata を保持し、`CHECK` を structural parent とする場合でも semantic source は upstream data node へ引き直すよう更新。
    - **ActionSynthesizer が exact upstream transform source を優先消費**:
        - `display_transform_ops` は `active_scope_item` より前に `transform_source_resolution` を見て、explicit `source_var` または `input_link` 由来の exact upstream var を優先するよう改善。
        - generic helper を `ActionSynthesizer` に追加し、`RETURN` と `TRANSFORM` の node-id based var 解決を共有化。
    - **TRANSFORM 回帰と運用文書を同期**:
        - `test_ir_generator` と `test_code_synthesizer_integration` に `TRANSFORM` provenance 回帰を追加し、exact upstream source が `active_scope_item` に吸収されないことを固定。
        - `cross_role_provenance_design.md`, `resolution_provenance_model.md`, `provenance_strength_policy_matrix.md`, `role_weakening_regression_table.md`, baseline regression run record を current `TRANSFORM` 観点に更新。
    - **ITERATE の collection-source continuity を固定**:
        - `src/ir_generator/iterate_resolution.py` を追加し、loop に `iteration_source_resolution` / `iteration_source_node_id` を付与するよう改善。
        - `ActionSynthesizer` の loop 処理は latest collection fallback より前に exact upstream collection を選ぶよう更新。
        - `test_ir_generator` と `test_code_synthesizer_integration` に `ITERATE` provenance 回帰を追加し、loop source が別 collection に吸収されないことを固定。
    - **ITERATE の item-side semantics を deterministic に補強**:
        - `iterate_resolution` が `iteration_item_entity` / `iteration_item_resolution` を保持するよう拡張し、collection inner type または deterministic history collection entity だけを採用するよう改善。
        - `ActionSynthesizer` の loop 処理は weak collection inner type より `iteration_item_entity` を優先するよう更新。
        - `test_ir_generator` と `test_code_synthesizer_integration` に item continuity 回帰を追加し、loop item 型が weak fallback に吸収されないことを固定。
    - **ITERATE の nested child continuity を loop history に接続**:
        - explicit `item_entity` を `iteration_item_entity` / `iteration_item_resolution=explicit_item_entity` として保持できるようにし、`context history.item_entity` として nested child へ引き継ぐよう改善。
        - `entity_inference` は通常の `target_entity` history より前に `item_entity` history を読むよう更新し、loop 内 child condition が weak `Item` に戻らず exact item entity を継承できるようにした。
        - `test_ir_generator` と `test_code_synthesizer_integration` に nested loop condition の回帰を追加し、`Points` 比較が `User` item context で deterministic に binding されることを固定。
    - **DISPLAY の item-side property provenance を追加**:
        - `src/ir_generator/display_resolution.py` を追加し、schema property / alias の exact match だけで `property` / `display_property_resolution` を付与するよう改善。
        - loop item continuity と組み合わせ、`名前を表示する` のような nested child display が weak `item` ではなく `item.Name` へ落ちるようにした。
        - `test_ir_generator` と `test_code_synthesizer_integration` に回帰を追加し、loop 内 display property continuity を固定した。
- **2026-05-13**:
    - **WRAP を explicit timeout wrapper まで一般化**:
        - `src/ir_generator/wrapper_resolution.py` を拡張し、explicit `wrapper_kind=timeout` または `timeout_ms/max_duration_ms/duration_ms` を持つ wrapper を deterministic に扱うよう改善。
        - timeout wrapper は `timeout_ms` と `timeout_resolution` を IR metadata として保持し、自然言語からの timeout 推定は行わない。
    - **IREmitter / CodeBuilder に timeout structural consumer を追加**:
        - `src/code_synthesis/ir_emitter.py` は `wrapper_kind=timeout` を `timeout` statement に再構成するよう更新。
        - `tools/csharp/CodeBuilder/Program.cs` と `src/utils/code_builder_client.py` は `timeout` statement を sync `Task.Run(...).Wait(TimeSpan)` / async `CancellationTokenSource + WaitAsync` へ展開するよう改善。
        - `CodeBuilderClient` は exe だけでなく対応する dll の更新時刻も見て Debug/Release を選ぶようにし、apphost lock 時の stale binary drift を避けるよう更新。
    - **WRAP timeout 回帰と研究文書を同期**:
        - `test_ir_generator` と `test_code_synthesizer_integration` に explicit timeout wrapper の IR 保持、runtime bridge、async timeout codegen の回帰を追加。
        - `wrap_timeout_semantics_design.md`, `structural_role_bridge.md`, `role_weakening_regression_table.md`, 関連 design docs を更新し、`WRAP` を retry/timeout の deterministic wrapper consumer として整理した。
    - **WRAP を explicit transaction wrapper まで一般化**:
        - `src/ir_generator/wrapper_resolution.py` を拡張し、explicit `wrapper_kind=transaction` を `transaction_resolution=explicit_transaction_wrapper` として保持するよう改善。
        - `IREmitter`, `CodeBuilderClient`, `tools/csharp/CodeBuilder/Program.cs` を更新し、`transaction` statement を sync/async `TransactionScope` へ決定論的に展開できるようにした。
        - `test_ir_generator` と `test_code_synthesizer_integration` に explicit transaction wrapper の IR 保持、runtime bridge、async `TransactionScope` codegen の回帰を追加。
        - `wrap_transaction_semantics_design.md`, `structural_role_bridge.md`, `role_weakening_regression_table.md`, 関連 design docs を更新し、`WRAP` を retry/timeout/transaction の deterministic wrapper consumer として整理した。
## 2026-05-15
- `midterm_synthesis`, `research_outcome_memo`, `goal_state` を更新し、`CHECK/FILTER/CALCULATE/RETURN/TRANSFORM/ITERATE/WRAP/DISPLAY` まで閉じた role 群として summary 層へ反映した。
- `remaining_open_inventory.md` を追加し、closed role / stable but not focus / open issues を研究の現時点として棚卸しした。

## 2026-05-22
- `scripts/validate_project_consistency.py` に `ai_project_map.json` の `source_file.path` / `design_document.path` / `test_file` 実在性チェックを追加し、docs / design / tests の同期漏れを検出できるようにした。
- `tests/integration/test_documented_entrypoints.py` に、`ai_project_map.json` 上の欠落 design 参照を validator が stderr へ出す回帰を追加した。
- `.github/workflows/python-ci.yml` を追加し、`tests.integration.test_documented_entrypoints`, `tests.security.test_security_vulnerabilities`, `scripts/validate_project_consistency.py` を GitHub Actions で自動実行するようにした。
- `.gitignore` を調整し、`.github/workflows` を追跡対象へ戻した。
- `tests/integration/test_documented_entrypoints.py` に `ComplexLinqSearch.design.md` を使った単体生成の決定論性回帰を追加し、固定設計書から同一コードが出ることを比較で固定した。
- `docs/README実装ギャップ段階改善計画.md` を更新し、Phase 4 の進捗として決定論性回帰と CI 導入を反映した。
- `tests/security/test_security_vulnerabilities.py` に `generate_from_design.py` の Safety Policy 回帰を追加し、禁止 intent、`--allow-unsafe` 時の `--confirm` 必須、command allowlist 違反を固定した。
- `docs/README実装ギャップ段階改善計画.md` を更新し、Phase 3 の残タスクだった安全ポリシー回帰の固定状況を反映した。
- README と `scripts/README.md` に CLI の stdout/stderr 契約を追記し、正式 CLI とデモ用スクリプトの境界を明文化した。
- `docs/README実装ギャップ段階改善計画.md` を更新し、Phase 3 の CLI 契約整理が概ね完了したことと残タスクを反映した。
- Phase 3 の残りとして `scripts/tools/manage_vector_db.py` を実装準拠に修正し、壊れていた `seed_system_methods` 依存を除去した。
- `manage_vector_db.py` は `--root` / `--analysis-path` を受け取り、`sync_method_store` の system method 定義を再利用して seed できるようにした。
- `manage_vector_db.py` は進行表示を stdout、analysis_output 未検出や harvest failure を stderr に分離した。
- `tests/integration/test_documented_entrypoints.py` に `manage_vector_db.py` の harvest failure と seed success 回帰を追加した。
- Phase 3 の stdout/stderr 契約を `scripts/generate_ir_case_summary.py` と `scripts/tools/suggest_method_capabilities.py` へ拡張した。
- `generate_ir_case_summary.py` は `--cases-dir` / `--output` を受け取り、生成成功を stdout、ケースディレクトリ未検出を stderr に分離した。
- `suggest_method_capabilities.py` は `--root` / `--store-path` / `--map-path` / `--out-dir` を受け取り、生成結果を stdout、method_store 未検出を stderr に分離した。
- `tests/integration/test_documented_entrypoints.py` に上記補助 CLI の回帰を追加した。
- Phase 3 の stdout/stderr 契約を `scripts/validate/run_unit_smoke.py`, `scripts/validate/run_ir_meaning_preservation_regression.py`, `scripts/validate/validate_ir_meaning_preservation_regression.py` へ拡張した。
- `run_unit_smoke.py` は `--test-target` を受け取り、成功時の unittest 出力を stdout、失敗時を stderr に分離するよう更新した。
- `run_ir_meaning_preservation_regression.py` は run file 未検出と step failure を stderr に寄せ、成功時の runner 出力は stdout に残すよう更新した。
- `validate_ir_meaning_preservation_regression.py` は成功レポートを stdout、run file 未検出や構造エラーを stderr に固定した。
- `tests/integration/test_documented_entrypoints.py` に上記 validate 系 3 本の回帰を追加した。
- Phase 3 の stdout/stderr 契約を `scripts/sync/sync_project_dependencies.py`, `scripts/validate/validate_method_store.py`, `scripts/tools/prune_backups.py` へ拡張した。
- `sync_project_dependencies.py` は `--root` を受け取り、同期完了を stdout、csproj 解析失敗を stderr に分離するよう更新した。
- `validate_method_store.py` は共通 CLI helper と `--strict` の argparse 化を導入し、失敗・警告を stderr、成功のみを stdout に固定した。
- `prune_backups.py` は `--root` を受け取り、dry-run/完了を stdout、backup ディレクトリ未検出や削除失敗を stderr に分離した。
- `tests/integration/test_documented_entrypoints.py` に上記 3 本の回帰を追加し、CLI 出力契約の維持を固定した。

## 2026-05-13
- `CALCULATE` の target-side provenance 4値を benchmark 上で閉じるため、`case_36_calculate_default_target_retention` と対応 observed IR を追加した。
- `calculate_case_observation`, `benchmark_cases`, case/result README を更新し、`default_target` は explicit `CALCULATE` だが target metadata を持たない weak-retention case で観測する境界を固定した。
- `CALCULATE` の target-side provenance 4値を benchmark 上でも閉じるため、`case_35_calculate_history_target_with_explicit_entity` と対応 observed IR を追加した。
- `calculate_case_observation`, `benchmark_cases`, case/result README を更新し、`history_target` は explicit entity を伴う ambiguous-owner contrast case で観測する境界を固定した。
- `CALCULATE` target-side provenance として `calculate_target_resolution` を追加し、`schema_property` / `history_target` / `explicit_target` / `default_target` を分離した。
- `calculate_resolution`, `IRGenerator`, `CALCULATE` tests、`calculate_case_observation` / role regression table / provenance 文書を同期した。
- `CALCULATE` source provenance に `default_scope_var` を追加し、exact source を materialize できないケースでも weak retention を観測可能にした。
- `calculate_resolution`, `ActionSynthesizer`, 関連 unit/integration tests、`calculate_case_observation` / provenance 設計文書 / role regression table を同期した。
