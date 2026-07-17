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

Run `asset-validation` manually from GitHub Actions. It performs two isolated
checks:

1. `semantic_method_search`: validates the chiVe and method-store hashes, then
   creates a Windows junction from the checkout's ignored `resources/vectors`
   directory to the pinned asset root, then runs real-vector and semantic-search
   tests. The workflow refuses to replace a checkout directory if it already
   exists.
2. `dictionary_search`: validates the dictionary hash.

The workflow is deliberately not triggered by push or pull request. A
GitHub-hosted runner does not have these optional local assets, and no asset is
downloaded or uploaded by this workflow.

If an asset intentionally changes, rebuild the manifest on the controlled
runner and review the resulting SHA-256 change before updating the repository
variable or running the workflow again.
