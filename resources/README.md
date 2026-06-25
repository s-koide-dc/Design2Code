# resources/ README

このディレクトリはAIのデータ資産を格納します。生成物は原則ここに集約されます。

注記:
- この文書は在庫表のため、`config/doc_reference_policy.json` では `existence_only_docs` として扱います。
- 下記の「生成物」は常に全てが存在するとは限りません。取得・変換後に現れる代表例として扱ってください。

## 0. 初期セットアップとの対応

README の「ベクトル/辞書の準備」で実行する主要コマンドと、増える代表生成物は次の通りです。

1. `python scripts/data/fetch_vectors.py`
   - `vectors/chive-1.3-mc90.txt`
2. `python scripts/data/convert_vectors.py`
   - `vectors/chive-1.3-mc90.txt.v0.vocab.npy`
   - `vectors/chive-1.3-mc90.txt.v0.matrix.npy`
3. `python scripts/data/fetch_jmdict.py`
   - `JMdict_e.gz`
   - `JMdict_e.xml`
4. `python scripts/data/parse_jmdict.py`
   - `dictionary.db`
5. `python scripts/data/build_knowledge_base.py`
   - `custom_knowledge.json` の再構築または更新
6. `python scripts/tools/manage_vector_db.py seed`
   - `vectors/vector_db/method_store_meta.json`
   - `vectors/vector_db/method_store_vectors.npy`
7. `python scripts/tools/manage_vector_db.py harvest`
   - `vectors/vector_db/repair_knowledge_meta.json`
   - `vectors/vector_db/repair_knowledge_vectors.npy`
   - `vectors/vector_db/structural_memory_meta.json`
   - `vectors/vector_db/structural_memory_vectors.npy`

## 1. 常設参照

- 文書自体: `resources/README.md`
- スキーマ: `schemas/ir_schema.json`
- 主要知識資産:
  - `method_store.json`
  - `intent_corpus.json`
  - `task_definitions.json`
  - `domain_dictionary.json`
  - `canonical_knowledge.json`

## 2. JMDict

- 取得元: `scripts/data/fetch_jmdict.py`
- 変換: `scripts/data/parse_jmdict.py`
- 生成物:
  - `JMdict_e.gz`
  - `JMdict_e.xml`
  - `dictionary.db` (SQLite + FTS)

## 3. ベクトル (chiVe)

- 取得: `scripts/data/fetch_vectors.py`
- 変換 (キャッシュ生成): `scripts/data/convert_vectors.py`
- 生成物:
  - `vectors/chive-1.3-mc90.txt`
  - `vectors/chive-1.3-mc90.txt.v0.vocab.npy`
  - `vectors/chive-1.3-mc90.txt.v0.matrix.npy`
  - `vectors/vector_db/`

## 4. Vector DB

- 保存先: `vectors/vector_db/`
- 生成物:
  - `method_store_meta.json`, `method_store_vectors.npy`
  - `repair_knowledge_meta.json`, `repair_knowledge_vectors.npy`
  - `structural_memory_meta.json`, `structural_memory_vectors.npy`

## 5. 知識ベース/辞書

- `custom_knowledge.json`
- `canonical_knowledge.json`
- `domain_dictionary.json`
- `intent_corpus.json`
- `task_definitions.json`
- `dependency_map.json`
- `method_store.json`

## 6. その他

- `entity_schema.json`
- `action_patterns.json`
- `repair_knowledge.json`
