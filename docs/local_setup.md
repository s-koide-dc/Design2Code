# ローカル初回セットアップ

このガイドは、必要な機能だけを段階的に有効化するための手順である。実モデル、ベクトルキャッシュ、`dictionary.db` はリポジトリへ含めない。GitHub Actions がこれらの資産なしで動作することは正常であり、ローカルで必要な能力だけを準備する。

最初に、どの能力が現在利用可能かを確認する。

```powershell
python scripts/validate/diagnose_local_environment.py
```

このコマンドはファイルを変更しない。不足した資産ごとに、次の準備コマンドを表示する。

GitHub Actions の `generation-smoke` は、モデル・ベクトルキャッシュ・`dictionary.db` を持たない新規runnerをセットアップ用サンドボックスとして使う。依存導入後に `--require design_generation` を通し、続く代表4件の生成回帰で実際のC#生成と静的品質を確認する。

## 1. 設計書からC#を生成する

必要なものは Python 3.13以上、Python依存、.NET SDK 10.0系、設定JSON、CodeBuilderソースである。実モデルと辞書は不要である。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/validate/diagnose_local_environment.py --require design_generation
python scripts/generate/generate_from_design.py --design scenarios/AppModeEchoMinimal.design.md
```

`.NET SDK` は `global.json` が指定する `10.0.109` 以上の安定版10.0系を使う。診断で `design_generation: ready` が表示されれば、設計書生成の前提は満たしている。

## 2. chiVeを使う対話・意味検索を有効にする

対話パイプラインや意味検索には、chiVe実モデルと2つのキャッシュが必要である。資産がある環境では、設計書の自然言語行からmethod-store・定石パターンを探索する候補拡張にも自動で使われる。候補の最終採否は設計書の構造・型・data source制約で行うため、モデルが無いCIでも同じ検証境界を保つ。

```powershell
python scripts/data/fetch_vectors.py
python scripts/data/convert_vectors.py
python scripts/validate/diagnose_local_environment.py --require semantic_pipeline
```

生成される資産は次の3つである。

- `resources/vectors/chive-1.3-mc90.txt`
- `resources/vectors/chive-1.3-mc90.txt.v0.vocab.npy`
- `resources/vectors/chive-1.3-mc90.txt.v0.matrix.npy`

実モデルを保持する環境では、続けて [実ベクトルモデル検証](real_vector_model_validation.md) を実行する。

準備できた資産を固定するには、次を一度実行する。manifest はローカルの
`logs/` 配下にだけ作られ、実資産や絶対パスはリポジトリへ追加されない。

```powershell
python scripts/validate/validate_local_asset_manifest.py --capability semantic_pipeline --write-manifest
python scripts/validate/validate_local_asset_manifest.py --capability semantic_pipeline
```

## 3. 意味的なmethod-store検索を有効にする

chiVeの準備後、method-storeベクトルDBを作成する。

```powershell
python scripts/tools/manage_vector_db.py seed
python scripts/validate/diagnose_local_environment.py --require semantic_method_search
```

必要な生成物は `resources/vectors/vector_db/method_store_meta.json` と `method_store_vectors.npy` である。

method-store まで使う場合は、依存するchiVe資産も含めて固定する。

```powershell
python scripts/validate/validate_local_asset_manifest.py --capability semantic_method_search --write-manifest
python scripts/validate/validate_local_asset_manifest.py --capability semantic_method_search
```

## 4. JMDictの辞書検索を有効にする

辞書検索・逆引き機能には、JMDictから作成する `resources/dictionary.db` が必要である。設計書生成の必須資産ではないが、ローカル資産プロファイルでは設計書の名詞に対応する語義を候補検索の文脈へ加え、日本語の設計文と既存ナレッジ内の英語混在記述を橋渡しする。

```powershell
python scripts/data/fetch_jmdict.py
python scripts/data/parse_jmdict.py
python scripts/validate/diagnose_local_environment.py --require dictionary_search
python scripts/validate/validate_local_asset_manifest.py --capability dictionary_search --write-manifest
```

## 5. ローカル検証の選び方

| 目的 | コマンド | 実モデルの要否 |
|---|---|---|
| 設定・依存・C#生成の前提確認 | `python scripts/validate/diagnose_local_environment.py --require design_generation` | 不要 |
| 資産なしサンドボックスでの初回セットアップ確認 | GitHub Actions の `generation-smoke` | 不要 |
| 軽量な単体確認 | `python scripts/validate/run_unit_smoke.py --profile core --verbosity 2` | 不要 |
| chiVe実モデルの読込・意味検索確認 | `python scripts/validate/validate_real_vector_model.py` | 必要 |
| 生成品質とruntime oracleの確認 | `python scripts/design/run_design_generation_regression.py --profile quality --fail-on-maintainability --run-runtime-oracles --require-runtime-oracles --summary-only` | 不要 |

資産と生成物の一覧は [resources/README.md](../resources/README.md) を参照する。
