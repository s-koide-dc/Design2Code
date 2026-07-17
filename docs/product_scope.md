# Product Scope and Maturity Boundary

## Product boundary

The supported product is a local, deterministic generator that transforms a
structured Japanese design document into C# code.  Its supported behaviour is
defined by [supported_generation_contract.md](./supported_generation_contract.md).

For a supported scenario, the project verifies the following with fixed design
documents, configuration, and generated fixtures:

1. the document can be parsed and converted into IR;
2. C# can be generated and pass the CodeBuilder/Roslyn maintainability gate;
3. an explicit runtime oracle, when present, passes after compilation and
   execution.

The product does not claim to accept arbitrary natural-language requirements,
schemas, SQL, or external services.  Missing semantic information must produce
a diagnostic or an `unverified` result rather than an invented implementation.

## Capability tiers

| Tier | Capability | Release expectation |
|---|---|---|
| Supported | Single design document to C# for the scenarios in the supported-generation contract | CI regression and explicit runtime-oracle coverage |
| Supported tooling | TDD CLI and documentation/design/test consistency validation | CLI and regression tests |
| Experimental | Conversation pipeline, semantic search, dictionary search, and multi-file project generation | No general correctness or availability guarantee; each use requires its stated local assets |

## Determinism and assets

Determinism applies only when the complete input set is fixed: the design
document, configuration, method metadata, vector assets when used, and the
generator version.  Model, dictionary, and generated vector assets are not
committed to this repository; their preparation and validation are described in
[local_setup.md](./local_setup.md) and
[real_vector_model_validation.md](./real_vector_model_validation.md).

Asset-dependent features must not be represented as asset-free CI guarantees.
They are validated in an environment that supplies the required assets.
The dedicated runner and manual workflow are defined in
[asset_validation.md](./asset_validation.md).

## Change admission

A new generation capability becomes supported only after it has all of the
following:

1. a representative `.design.md` scenario;
2. explicit, machine-checkable runtime expectations where runtime behaviour is
   claimed;
3. regression coverage in the generation-quality workflow; and
4. an update to the supported-generation contract.

This keeps the supported surface intentional while allowing experimental
modules to evolve without overstating their maturity.

## Quality baseline

The supported generation path has a CI coverage-baseline job for
`design_parser`, `ir_generator`, `code_synthesis`, and `code_verification`.
The job publishes measurement data but does not yet reject a change based on a
single repository-wide percentage.  A threshold may be admitted only after the
baseline is stable and its scope represents the supported-generation contract.
