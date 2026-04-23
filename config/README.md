# config/ README

このディレクトリは挙動・ポリシー・運用設定を格納します。  
実行時は `src/config/config_manager.py` がこの配下の JSON を読み込みます。

## 1. 基本設定

- `config.json`  
  中核設定。タスク管理や推論に関する共通セクションを保持。

- `user_preferences.json`  
  ユーザー指向のデフォルト設定（対話・出力の傾向）。

## 2. ポリシー/ルール

- `safety_policy.json`  
  安全性や拒否条件の基準。

- `retry_rules.json`  
  再試行条件・回復フローの定義。

- `project_rules.json`  
  プロジェクト生成や構成制約。

- `scoring_rules.json`  
  ルールベースの評価基準（品質判定など）。

## 3. 解析/生成の補助設定

- `error_patterns.json`  
  エラー判定や診断用のパターン。

- `coverage_config.json`  
  カバレッジ解析の設定。

- `refactoring_config.json`  
  リファクタリング分析の設定。

- `cicd_config.json`  
  CI/CD 連携・生成の設定。

- `synthesis_profile.json`  
  生成プロファイル（生成方針や重み付け）。

- `autonomous_learning.json`  
  自律学習の動作設定。

## 4. 実行時の一時/可変設定

- `current_project_context.json`  
  実行中のプロジェクト状態を保持する一時ファイル。

## 5. 変更時の注意

- 既存のキーを削除・改名する場合は、`src/config/config_manager.py` と参照箇所を同時に更新してください。
- 生成や解析の分岐に影響する設定は、テストでの再確認が必須です。
