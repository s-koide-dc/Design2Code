# Optional Asset Validation

## Purpose

The standard GitHub-hosted CI workflow intentionally runs without chiVe,
JMDict, and generated method-store assets. This workflow validates those local
assets only on a dedicated self-hosted runner, after first checking their
hash-pinned manifest.

## Runner requirements

The runner must have both the `self-hosted` and `nlp-assets` labels, Python
3.13, .NET SDK 10.0.109, and the optional assets prepared according to
[local_setup.md](./local_setup.md).

Prepare a durable asset root outside the checked-out repository. It must retain
the same relative layout as the repository (for example,
`D:\NlpAssets\resources\vectors\...`). Create the manifest once on that
runner:

```powershell
python scripts/validate/validate_local_asset_manifest.py --workspace-root D:\NlpAssets --capability semantic_method_search --capability dictionary_search --write-manifest --manifest D:\NlpAssets\local_asset_manifest.json
```

Set the repository Actions variable `NLP_ASSET_MANIFEST_PATH` to that manifest
path and `NLP_ASSET_WORKSPACE_ROOT` to the durable asset root. These paths are
configuration only; they must not contain credentials. The manifest itself
contains relative asset paths, sizes, and SHA-256 values, not asset contents or
absolute asset paths.

## Running the workflow

Run `asset-validation` manually from GitHub Actions. It validates both
`semantic_method_search` and `dictionary_search` against the pinned manifest,
then creates a Windows junction for the ignored `resources/vectors` directory
and copies the dictionary database into the isolated checkout. The workflow
refuses to replace a checkout vector directory if it already exists.

It then runs `run_local_semantic_quality_gate.py` and every integration test
listed in `tests/ci_test_matrix.json` under `integration.ci_excluded`. This
keeps the GitHub-hosted job asset-free while making the otherwise-excluded
documented-entrypoint, semantic-search, vector, conversation, end-to-end, and
reverse-lookup paths mandatory on the controlled asset runner. The report is
written to the runner's temporary directory and covers real-vector loading,
semantic method search, JMDict lookup, and asset-backed natural-language
numeric predicate generation. No report or asset is uploaded to GitHub.

The workflow is deliberately not triggered by push or pull request. A
GitHub-hosted runner does not have these optional local assets, and no asset is
downloaded or uploaded by this workflow.

If an asset intentionally changes, rebuild the manifest on the controlled
runner and review the resulting SHA-256 change before updating the repository
variable or running the workflow again.
