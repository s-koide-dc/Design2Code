# Asset Manifest Design

## Purpose

任意ローカル資産の能力別要件を読み取り、サイズとSHA-256で固定したmanifestを生成・検証する。実資産の内容、絶対パス、秘密情報はmanifestへ保存しない。

## Input / Output

- Input: ワークスペースroot、`asset_requirements.json`、選択capability、既存manifest。
- Output: schema version、相対asset path、size、SHA-256を含むmanifest、または不一致一覧。

## Rules

1. capability依存をたどり、必要assetを重複なく収集する。
2. asset pathはworkspace内の通常ファイルだけを受け入れる。
3. manifest検証では要件とのasset集合、相対path、size、SHA-256を照合する。
4. 欠落資産、不正schema、循環依存、workspace外pathは明示エラーにする。

## Dependencies

- Standard library: `hashlib`, `json`, `pathlib`.
- Caller: `scripts/validate/validate_local_asset_manifest.py`.
