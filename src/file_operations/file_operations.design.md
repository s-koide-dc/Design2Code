# FileOperations Design Document

## 1. Purpose
`FileOperations` は、独立したモジュールとして、ファイルシステムの基本的な操作（作成、読み込み、削除、移動、コピーなど）を安全に実行する責任を負います。リトライ機構と詳細なエラーハンドリングにより、堅牢なファイル操作を提供します。

## 2. Structured Specification

### 2.1. 初期化 (`__init__`)
- **Parameters**: `action_executor` - 親となる ActionExecutor インスタンス (移行期間中)
- **Logic**: ActionExecutor への参照を保持し、`_get_entity_value` や `_safe_join` などのヘルパーメソッドにアクセスできるようにします。将来的にこれらはユーティリティクラスへ委譲される予定です。

### Input
- **context** (Dict[str, Any]): パイプライン・コンテキスト。
- **parameters** (Dict[str, Any]): 
    - `filename`: 対象ファイル名（create_file, append_file, delete_file, read_file で使用）
    - `content`: ファイルの内容（create_file, append_file で使用）
    - `source_filename`: 移動/コピー元（move_file, copy_file で使用）
    - `destination_filename`: 移動/コピー先（move_file, copy_file で使用）
    - `directory`: 一覧表示対象ディレクトリ（list_dir で使用、デフォルトは "."）

### Output
- **context** (Dict[str, Any]): 処理結果（`action_result`）を含む更新されたコンテキスト。
  - `action_result["status"]`: "success" または "error"
  - `action_result["message"]`: 操作結果のメッセージ
  - `action_result["content"]`: ファイル内容（read_file の場合のみ）

### Core Logic

#### 2.2. ファイル作成 (`create_file`)
1. パラメータから `filename` と `content` を取得します。
2. `filename` が指定されていない場合はエラーを返します。
3. **セキュリティ & 制限**: 
   - コンテンツのサイズが **10MB** を超える場合は、リソース保護のためエラーを返します。
   - `_safe_join` により、ワークスペース外のパスや UNC パスをブロックします。
4. ファイルを **UTF-8** エンコーディングで書き込みます。
5. **堅牢性**: `@retry_with_backoff(max_retries=3)` デコレータにより、一時的な OS レベルのエラー時に自動リトライを行います。

#### 2.3. ファイル追記 (`append_file`)
1. パラメータから `filename` と `content` を取得します。
2. `filename` が指定されていない場合、またはファイルが存在しない場合はエラーを返します。
3. **サイズ制限**: 追記後の合計ファイルサイズが **10MB** を超える場合はエラーを返します。
4. ファイルの末尾に改行を追加してからコンテンツを追記します。
5. `create_file` と同様のリトライ機構を備えています。

#### 2.4. ファイル削除 (`delete_file`)
1. パラメータから `filename` を取得します。
2. ファイルまたはディレクトリが存在しない場合はエラーを返します。
3. **ディレクトリ判定**: 対象がディレクトリの場合は `shutil.rmtree` で再帰的に削除し、ファイルの場合は `os.remove` で削除します。
4. 例外処理により、権限エラーや OS エラーを適切にハンドリングします。

#### 2.5. ファイル読み込み (`read_file`)
1. パラメータから `filename` を取得します。
2. ファイルが存在しない場合は `FileNotFoundError` を発生させます。
3. ファイルを UTF-8 エンコーディングで読み込みます。
4. **プレビュー機能**: メッセージには先頭500文字のみを含め、完全な内容は `action_result["content"]` に格納します。
5. `UnicodeDecodeError` を含む各種例外を適切にハンドリングします。

#### 2.6. ディレクトリ一覧 (`list_dir`)
1. パラメータから `directory` を取得します（デフォルトは "."）。
2. ディレクトリが存在しない場合はエラーを返します。
3. `os.listdir` でディレクトリ内のアイテムを取得します。
4. **表示制限**: 最大20件のアイテムをメッセージに含めます。

#### 2.7. ファイル移動 (`move_file`)
1. パラメータから `source_filename` と `destination_filename` を取得します。
2. 両方のパスの安全性を検証します。
3. **ディレクトリ自動作成**: 移動先のディレクトリが存在しない場合は自動的に作成します。
4. `shutil.move` でファイルを移動します。
5. リトライ機構と例外処理を実装しています。

#### 2.8. ファイルコピー (`copy_file`)
1. パラメータから `source_filename` と `destination_filename` を取得します。
2. 両方のパスの安全性を検証します。
3. **ディレクトリ自動作成**: コピー先のディレクトリが存在しない場合は自動的に作成します。
4. **ディレクトリ判定**: コピー元がディレクトリの場合は `shutil.copytree` で再帰的にコピーし、ファイルの場合は `shutil.copy2` でコピーします（メタデータも保持）。
5. リトライ機構と例外処理を実装しています。

### Test Cases

#### Happy Path
- **create_file**: 有効なパスと内容を指定し、ファイルが正常に作成されること。
- **append_file**: 既存ファイルに内容が正常に追記されること。
- **delete_file**: ファイルとディレクトリが正常に削除されること。
- **read_file**: ファイルの内容が正常に読み込まれ、プレビューと完全な内容が返されること。
- **list_dir**: ディレクトリの内容が正常に一覧表示されること。
- **move_file**: ファイルが正常に移動され、移動先ディレクトリが自動作成されること。
- **copy_file**: ファイルとディレクトリが正常にコピーされること。

#### Edge Cases
- **create_file**: 10MB を超えるコンテンツの書き込みがエラーになること。
- **append_file**: 追記後のファイルサイズが 10MB を超える場合にエラーになること。
- **delete_file**: 存在しないファイルの削除がエラーになること。
- **read_file**: UTF-8 でエンコードされていないファイルの読み込みが適切なエラーメッセージを返すこと。
- **move_file/copy_file**: 無効なパス（ワークスペース外）へのアクセスがブロックされること。
- **全操作**: 権限エラーが適切にハンドリングされること。

## 3. Dependencies
- **Internal**: `ActionExecutor` (移行用依存)、`retry_utils.retry_with_backoff`
- **External**: `os`, `shutil`, `typing`

## 4. Error Handling
- **PermissionError**: 権限不足を示す明確なメッセージ
- **FileNotFoundError**: ファイルが見つからないことを示すメッセージ
- **OSError**: OS レベルのエラーを示すメッセージ
- **UnicodeDecodeError**: 文字コードの問題を示すメッセージ
- **一般的な Exception**: 予期しないエラーのキャッチとログ記録

## 5. Retry Mechanism
`create_file`, `append_file`, `move_file`, `copy_file` には `@retry_with_backoff(max_retries=3)` デコレータが適用されており、一時的なファイルシステムエラー（ロック、一時的なアクセス拒否など）に対して自動的にリトライします。
