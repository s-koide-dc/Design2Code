# context_manager Design Document

## 1. Purpose
`context_manager`モジュールは、AIパイプラインのためのシンプルな「短期記憶」を提供します。最近の会話コンテキストを固定サイズのキューで維持します。この履歴は、セマンティックアナライザーなどの他のモジュールで利用可能になり、タスクの実行に使用されます。

## 2. Structured Specification

### Input
- **For `add_context(context: dict)`**:
  - **Description**: パイプラインの全ステージが完了した後のコンテキスト辞書。`session_id` キーが含まれている必要があります。
- **For `get_history(session_id: str)`**: セッションIDを指定します。
- **For `get_last_context(session_id: str)`**: セッションIDを指定します。

### Output
- **For `add_context`**: `None`（内部状態が更新されます）。
- **For `get_history`**:
  - **Description**: 指定されたセッションに関連付けられた履歴コンテキストエントリーのリスト。
- **For `get_last_context`**:
  - **Description**: 指定されたセッションの最新エントリーオブジェクト。履歴が空の場合は `None` を返します。

### Core Logic
1.  **セッション分離された履歴の保存 (`add_context`)**: 
    - コンテキストから `session_id` を取得し、そのセッション専用の履歴リスト（`self.history[session_id]`）にサマリーを追加します。
2.  **履歴の整理（対話ターン制限）**: 
    - 各セッションごとに `max_history` を超えた古いエントリーを自動的に削除します。
3.  **実行確認待ちプランの管理 (Session-aware)**:
    - `set_pending_confirmation_plan(session_id, plan)`: 特定のセッションに対して承認待ちプランを保存します。
    - `get_pending_confirmation_plan(session_id)` / `clear_pending_confirmation_plan(session_id)`: セッションごとにプランを操作します。
4.  **フィードバック待ち状態の管理**:
    - `set_awaiting_feedback(session_id, is_awaiting)`: セッションがユーザーからのフィードバック詳細を待機しているかどうかを設定します。
    - `is_awaiting_feedback(session_id)`: 現在の状態を取得します。これにより、パイプラインは通常のインテント解析をスキップしてフィードバック収集へフローを切り替えることができます。

### Test Cases
- **Scenario**: Get History (Empty)
    - **Input**:
      ```json
      {
        "target_method": "get_history",
        "init_args": {"max_history": 10},
        "args": {"session_id": "new_session"}
      }
      ```
    - **Expected**:
      ```json
      []
      ```
- **Scenario**: Add Context and Retrieve
    - **Input**:
      ```json
      {
        "target_method": "get_last_context",
        "init_args": {"max_history": 10},
        "setup_code": [
            "context = {'session_id': 'test_session', 'original_text': 'input', 'analysis': {'intent': 'TEST'}}",
            "self.target.add_context(context)"
        ],
        "args": {"session_id": "test_session"}
      }
      ```
    - **Expected**:
      ```json
      {
        "intent": "TEST",
        "original_text": "input"
      }
      ```
- **Scenario**: Max History Limit
    - **Input**:
      ```json
      {
        "target_method": "get_history",
        "init_args": {"max_history": 2},
        "setup_code": [
            "self.target.add_context({'session_id': 'sess', 'original_text': '1'})",
            "self.target.add_context({'session_id': 'sess', 'original_text': '2'})",
            "self.target.add_context({'session_id': 'sess', 'original_text': '3'})"
        ],
        "args": {"session_id": "sess"}
      }
      ```
    - **Expected**:
      ```json
      [
        {"original_text": "2"},
        {"original_text": "3"}
      ]
      ```

## 4. Consumers
- **pipeline_core**: Uses ContextManager to maintain session history and inject it into the analysis context.

## 3. Dependencies
- **Internal**: `pipeline_core`
- **External**: なし
