# README 実装ギャップ段階改善計画

この計画は [AIFiles/PROJECT_CHARTER](/C:/workspace/NLP/AIFiles/PROJECT_CHARTER.md) と [AIFiles/CONVENTIONS.md](/C:/workspace/NLP/AIFiles/CONVENTIONS.md)、および `docs/改善指示.pdf` を前提に、README と実装の温度差を段階的に縮めるための実行順を整理したものです。

注記:
- この文書は段階改善のための作業計画メモであり、恒久公開 docs と同じ validator 必須監視対象には含めない。
- 必要なら `config/doc_reference_policy.json` の `required_docs` へ昇格させる。
- 現在は `optional_reference_docs` 扱いなので、文書が存在する場合はローカル参照整合だけ validator 対象になる。

## 方針
- 一度に全面改修しない。
- まず「README が約束している導線」を実装事実へ揃える。
- 次に、README に載せたい体験を実装側で増やす。
- スコアリングやキーワード当ての場当たり対応ではなく、既存の設計書駆動・決定論方針に沿って改善する。

## Phase 1: 公開導線の実装整合
- 目的: README の主張を現行実装に合わせる。
- 対象:
  - 決定論性の説明を「固定資産前提」に修正する。
  - 対話パイプラインの例を、実際に確認できた入力へ差し替える。
  - TDD CLI と設計書生成 CLI の動線をスモークテストで固定する。
- 完了条件:
  - README の例が手元環境で再現できる。
  - `tests/integration/test_documented_entrypoints.py` が通る。

## Phase 2: 対話パイプラインの期待値整理と実力向上
- 目的: README に載せたい対話例と、実際の intent 解決能力を近づける。
- 対象:
  - `GET_CWD` のような既存成功ケースを基準入力として整理する。
  - 現在 clarification に落ちる代表入力を棚卸しする。
  - `intent_detector` / `planner` / `clarification_manager` の境界で、設計書とずれている箇所を修正する。
- 完了条件:
  - README に載せる対話例が 2 から 3 個は自動テストで保証される。
  - 曖昧入力は曖昧なまま止め、確定入力だけを安全に実行する。

## Phase 3: エラーハンドリングと安全ポリシーの統一
- 目的: `docs/改善指示.pdf` の「統一的な例外処理・ログ出力」を実装に落とす。
- 対象:
  - 主要 CLI の stdout/stderr 契約を [docs/stdout_output_policy.md](/C:/workspace/NLP/docs/stdout_output_policy.md) に合わせる。
  - 安全ポリシー違反時のエラーメッセージとログ項目を共通化する。
  - `tests/security` に安全ポリシー違反時の回帰テストを追加する。
- 完了条件:
  - 代表的な失敗経路で、利用者向けメッセージと内部ログの責務が分離される。
  - 安全ポリシー違反の検出がテストで固定される。
 - 進捗メモ:
   - 主要 CLI と補助 CLI の stdout/stderr 分離は概ね完了。
   - `tests/security` に `generate_from_design.py` の禁止 intent / override confirm / command allowlist 回帰を追加済み。
   - 未完了の中心は、必要なら planner / pipeline 経由の安全ポリシー回帰を追加する段階。

## Phase 4: 決定論性回帰と CI 固定
- 目的: 「再現可能な生成」を README の説明だけでなく検証資産にする。
- 対象:
  - 同一設計書から同一コードが出る回帰テストを追加する。
  - `scripts/validate_project_consistency.py` と主要テストを CI で自動実行する。
  - docs / design / tests の同期漏れを検知する。
- 完了条件:
  - 代表シナリオで生成結果差分が自動検出される。
  - README に載せた公開導線が CI でも継続検証される。
 - 進捗メモ:
   - `ComplexLinqSearch.design.md` を使った単体生成の決定論性回帰を追加。
   - `.github/workflows/python-ci.yml` を追加し、公開導線回帰・security・整合性チェックを自動化。
   - CI に `scripts/validate/run_unit_smoke.py --verbosity 2` を追加し、主要 unit smoke も継続検証対象にした。
   - `run_unit_smoke.py` の既定対象を軽量 unit 群まで広げ、config/design parser/dependency/json guard も smoke に含めた。
   - `run_unit_smoke.py` に `core` / `parser` / `synthesis` profile を追加し、CI は default のまま維持しつつローカルではカテゴリ単位に切り出せるようにした。
   - CI 非依存化のため vector cache 確認を `assets` profile へ分離し、workflow では asset 非依存 profile だけを明示実行する形へ調整した。
   - `validate_project_consistency.py` に `ai_project_map.json` の source/design/test 参照先実在性チェックを追加し、同期漏れを stderr で検出できるようにした。
   - `README.md` / `scripts/README.md` / `docs/stdout_output_policy.md` のローカル参照実在性チェックを追加し、公開文書のリンクずれを validator で検出できるようにした。

## 現在の着手範囲
- Phase 1 と Phase 2 は実施済み。
- Phase 3 は CLI 出力契約の整理をほぼ完了。
- 次の主対象は、Phase 4 の docs 整合検知を README 以外の主要文書へ広げたうえで、必要に応じて CI のテスト範囲を広げる段階。
