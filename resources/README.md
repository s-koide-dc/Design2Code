# resources/ README

このディレクトリはAIのデータ資産を格納します。生成物は原則ここに集約されます。

## 1. JMDict

- 取得元: `scripts/data/fetch_jmdict.py`
- 変換: `scripts/data/parse_jmdict.py`
- 生成物:
  - `JMdict_e.gz`
  - `JMdict_e.xml`
  - `dictionary.db` (SQLite + FTS)

## 2. ベクトル (chiVe)

- 取得: `scripts/data/fetch_vectors.py`
- 変換 (キャッシュ生成): `scripts/data/convert_vectors.py`
- 生成物:
  - `vectors/chive-1.3-mc5.txt`
  - `vectors/chive-1.3-mc5.txt.v200000.vocab.npy`
  - `vectors/chive-1.3-mc5.txt.v200000.matrix.npy`

## 3. Vector DB

- 保存先: `vectors/vector_db/`
- 生成物:
  - `method_store_meta.json`, `method_store_vectors.npy`
  - `repair_knowledge_meta.json`, `repair_knowledge_vectors.npy`
  - `structural_memory_meta.json`, `structural_memory_vectors.npy`

## 4. 知識ベース/辞書

- `custom_knowledge.json`
- `canonical_knowledge.json`
- `domain_dictionary.json`
- `intent_corpus.json`
- `task_definitions.json`
- `dependency_map.json`
- `method_store.json`

## 5. その他

- `entity_schema.json`
- `action_patterns.json`
- `repair_knowledge.json`

## 6. スキーマ

- `schemas/ir_schema.json`
