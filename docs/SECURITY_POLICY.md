# セキュリティポリシー

## 1. 目的
本ドキュメントは、ローカル対話応答AIプロジェクトのセキュリティ方針を定義し、セキュリティに関わる挙動を明示・追跡可能にする。

## 2. 適用範囲
本ポリシーは以下に適用する:
- アクションの計画・実行（ファイル操作、コマンド実行）。
- ログにおける機密情報の取り扱い。
- セキュリティに影響する入力解析（パス解析、正規表現利用等）。
- セキュリティ関連のテストと検証要件。

## 3. リスク分類と承認
システムは実行前に意図（intent）をリスクレベルに分類する。

### 3.1 高リスク（承認必須）
以下の intent は高リスクとみなし、実行前に明示的なユーザー承認が必要:
- `FILE_DELETE`
- `FILE_MOVE`
- `BACKUP_AND_DELETE`
- `APPLY_CODE_FIX`
- `APPLY_REFACTORING`
- `FILE_APPEND`
- `CMD_RUN`

### 3.2 中リスク（注意）
以下の intent は注意対象。ポリシー次第で承認なし実行も可:
- `FILE_CREATE`

### 3.3 低リスク
その他はデフォルトで低リスクとする（必要に応じて変更）。

承認の強制:
- `confirmation_needed` が true の場合、`confirmation_granted`（または `confirmed`）が明示的に true でない限り実行をブロックする。
対話型でない入口（設計書→コード生成など）で安全チェックをバイパスする場合は、`--confirm` などの CLI フラグで明示承認すること。

## 3.4 承認フロー（状態遷移）

リスクのあるアクションに対する承認の要求・付与・強制の流れを定義する。

状態:
- `NO_APPROVAL_REQUIRED`: 承認不要。
- `AWAITING_APPROVAL`: `confirmation_needed` が true の計画がある状態。
- `APPROVED`: ユーザーが明示的に承認した状態。
- `REJECTED`: ユーザーが明示的に拒否した状態。

状態遷移:
1. `NO_APPROVAL_REQUIRED` → `AWAITING_APPROVAL`
   - トリガー: Planner が `confirmation_needed = true` の計画を作成。
2. `AWAITING_APPROVAL` → `APPROVED`
   - トリガー: ユーザーが承認意図（`AGREE`）を返し、保留計画が復元される。
   - アクション: 実行コンテキストに `confirmation_granted = true` を設定。
3. `AWAITING_APPROVAL` → `REJECTED`
   - トリガー: ユーザーが拒否意図（`DISAGREE`）を返す。
   - アクション: 保留計画を破棄し、実行をキャンセル。
4. `APPROVED` → `NO_APPROVAL_REQUIRED`
   - トリガー: 実行が完了し、完了ログを記録。
5. `REJECTED` → `NO_APPROVAL_REQUIRED`
   - トリガー: キャンセル通知をユーザーへ返す。

強制ルール:
- `confirmation_needed` が true で `confirmation_granted` が未設定の場合、Executor は実行をブロックする。

`--allow-unsafe` の運用ルール:
- 許可ケース: 危険 intent を含む設計の監査目的／隔離された検証環境のみ。
- 禁止ケース: 本番/実作業環境、出所不明の設計、CI 等のデフォルト動作。
- 推奨: 通常運用では使わない。使用時は `--confirm` を必須とし、理由をログに残す。

## 4. コマンド実行ポリシー（`CMD_RUN`）
コマンド実行は二段階で制御する:

1. **Planner レベル検証**: `SafetyPolicyValidator`
2. **実行レベル検証**: `ActionExecutor._run_command`

### 4.1 ベースコマンドのホワイトリスト
許可されたコマンドのみ実行可能。

**正本**: `config/safety_policy.json`  
キー: `safe_commands`

### 4.2 サブコマンド制限
一部のコマンドはサブコマンドの allowlist を要求する。

許可サブコマンド:
- `git`: `status`, `log`, `diff`, `show`, `branch`, `rev-parse`, `ls-files`
- `dotnet`: `test`, `build`, `restore`, `clean`, `list`
- `npm`: `test`, `list`

サブコマンド検証不要:
- `dir`, `ls`, `echo`, `type`, `cat`, `date`, `time`, `py`, `python`
補足: `safe_commands` に含まれていて `allowed_subcommands` に無いコマンドは、サブコマンド検証なしで許可されるが、メタ文字検証は適用される。

### 4.3 メタ文字ブロック
次の文字を含む場合、インジェクション対策としてブロックする:
`&` `|` `;` `>` `<` ``` ` ``` `$`

### 4.4 禁止オプション
ベースコマンドが許可されていても、明示的に禁止するオプションがある。
- `python`: `-c`
- `py`: `-c`

### 4.5 Python スクリプト制限
`python`/`py` はワークスペース内の `scripts/` 配下スクリプトのみ実行可能。
`-c` と `-m` は禁止（インライン/モジュール実行防止）。
`python_allowed_scripts` が定義されている場合は、明示 allowlist に限定する。

### 4.6 読み取り/一覧コマンド制限
読み取りコマンド（`cat`, `type`）はパス指定必須で `read_allowed_dirs` に限定する。
一覧コマンド（`ls`, `dir`）はパス指定時に `read_allowed_dirs` に限定する。
現行は `AIFiles`, `config`, `docs`, `scripts`, `src`, `tests` のみ許可。
`read_blocked_rules` に一致するパスは、許可ディレクトリ配下でも拒否する。
既定ルールは `.env` を basename 完全一致で拒否し、`secret`/`token` はファイル名トークン一致のみ拒否する。

### 4.7 実行モード
コマンドは `shell=False` で実行する。  
Windows のビルトインは `cmd /c` 経由で実行する。

## 5. allowlist 正規化ルール
allowlist 判定は以下の正規化ルールに従う:
- `realpath` で実体パスを解決し、ワークスペースルート基準で評価する。
- 相対パスはワークスペースルート基準で解釈する。
- 大小文字は OS/ファイルシステムの挙動に従う。
- シンボリックリンクは解決した実体パスで評価する。
- UNC パスおよびワークスペース外パスは常に拒否する。

## 5. ファイルシステムポリシー
すべてのファイル操作はワークスペースルート内に限定する。

### 5.1 パス検証
`realpath` で解決し、以下を拒否:
- ワークスペース外パス
- Windows の UNC パス
- NULL バイトを含むパス

### 5.2 ファイルサイズ制限
作成/追記後のファイルサイズは **10MB** を超えてはならない。

## 6. ログと監査ポリシー

### 6.1 機密フィールドのマスキング
以下のフィールドは常にマスクする:
- `filename`
- `command`
- `content`
- `error_details`
正本: `config/config.json` → `logging.sensitive_fields`
加えて、キー名に機密キーワード（例: `token`, `secret`, `password`）を含む場合もマスクする。

### 6.2 監査要件（セキュリティイベント）
セキュリティ重要イベントは以下の必須フィールドを要求する:
- `parameters`
- `status`

要件を満たさず strict audit が有効な場合は監査違反としてエラーとする。

## 7. セキュリティテスト
セキュリティ検証は以下で実施する:
`tests/security`

現行のカバレッジ:
- ログの秘匿化
- ReDoS 対策
- パストラバーサル防止（相対/絶対/UNC）
- コマンド注入防止・サブコマンド制限

## 8. 変更管理
セキュリティ関連の変更時は:
1. 本ポリシー更新
2. セキュリティテスト更新/追加
3. セキュリティテスト再実行

## 9. 絶対禁止事項（非バイパス）
以下は `--allow-unsafe` でも解除不可:
- ワークスペース外パス（UNC を含む）。
- メタ文字を含むコマンド引数（`&`, `|`, `;`, `>`, `<`, `` ` ``, `$`）。
- `python/py` の `-c` / `-m` 実行。

## 10. 高リスク変更のバックアップ必須化
以下の intent は実行前に必ずバックアップを作成する:
- `FILE_DELETE`
- `APPLY_CODE_FIX`
- `APPLY_REFACTORING`
バックアップに失敗した場合、実行はブロックする。

### 10.1 バックアップ保持ポリシー
- **保存先**: ワークスペースルート配下の `backup/`
- **命名**: `{original_filename}.{YYYYMMDD_HHMMSS}.bak`
- **保持**: 直近30日またはソースごとに最大50件（小さい方）
- **削除**: 運用者またはメンテナンスタスクで整理

## 11. 既知のギャップ（追跡中）
ポリシーは Planner と Executor の二段階で適用する。  
両者の allowlist に差異がある場合はリリース前に解消すること。
