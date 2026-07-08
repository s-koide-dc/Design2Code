# 実ベクトルモデル検証

## 方針

実ベクトルモデルと派生キャッシュはリポジトリへ配置しない。GitHub Actions はモデル非依存のテストのみを実行し、実モデル検証はモデルを保持するローカル環境または専用実行環境で行う。

## 前提

`ConfigManager.vector_model_path` が示す場所に次の3ファイルを配置する。

- 実モデル
- `<model>.v0.vocab.npy`
- `<model>.v0.matrix.npy`

## 実行

```powershell
python scripts/validate/validate_real_vector_model.py
```

各テストの上限時間を変更する場合:

```powershell
python scripts/validate/validate_real_vector_model.py --timeout-seconds 600
```

## 結果

既定では `logs/real_vector_validation.json` に以下を記録する。

- モデルのファイル名、サイズ、更新日時、SHA-256
- Pythonバージョンと実行日時
- 実モデル読込テストと意味検索テストの成否、所要時間、出力末尾

絶対パスやモデル内容は記録しない。終了コードは成功時 `0`、テスト失敗時 `1`、必要ファイル不足時 `2` とする。
