# Semantic Repair Memory (Phase 3)

## 1. Purpose
`RepairKnowledgeBase` を拡張し、従来の文字列マッチングからベクトル検索（Semantic Search）へ移行します。これにより、エラーメッセージの微細な違い（タイムスタンプやファイルパスの差異など）に左右されず、本質的に類似した過去のトラブルと解決策を特定できるようになります。

## 2. Structured Specification

### Input
- **Error Description**: 発生したエラーメッセージ。
- **Fix Experience**: 成功した修正の記録（原因、エラー、適用した修正）。
- **VectorEngine**: テキストをベクトル変換するためのエンジン。

### Output
- **Semantic Match**: 過去の事例の中で最も類似度の高い修正方針。
- **Similarity Score**: マッチングの信頼度（0.0〜1.0）。

### Core Logic

#### A. 知識の蓄積 (Learning)
1.  **ベクトル化**: 新しい成功体験を記録する際、エラーメッセージを `VectorEngine` を用いて多次元ベクトルに変換する。
2.  **エピソード保存**:
    - `repair_knowledge.json`: メタデータ（テキスト、修正方針、統計）を保存。
    - `repair_vectors.npy`: 高速検索用のベクトル行列を保存。

#### B. 類似事例の検索 (Inference)
1.  **クエリ変換**: 入力されたエラーメッセージをベクトルに変換。
2.  **ベクトル検索**: 蓄積された `repair_vectors` 行列に対して、クエリベクトルとのコサイン類似度を一括計算。
3.  **しきい値判定**: 
    - 最大類似度が `semantic_threshold` (例: 0.85) を超える場合、その事例の `fix_direction` を返す。
    - 超えない場合は、従来の文字列マッチングにフォールバック、または「未知のエラー」として扱う。

### Test Cases
- **Scenario**: 類似エラーの検知
    - **Input**: "Expected 'A' but found 'B'" (過去に "Expected 'X' but found 'Y'" で成功例あり)
    - **Expected**: 過去の修正方針が提案されること。
- **Scenario**: 低類似度の除外
    - **Input**: 全く関係のないエラーメッセージ。
    - **Expected**: `None` を返し、誤った提案を避けること。
