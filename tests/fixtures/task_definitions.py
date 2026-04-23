# -*- coding: utf-8 -*-
# tests/fixtures/task_definitions.py

"""
共通のテスト用タスク定義
テストファイル間での重複を避け、保守性を向上させる
"""

COMMON_TASK_DEFINITIONS = {
    "FILE_CREATE": {
        "states": ["INIT", "AWAITING_FILENAME", "AWAITING_CONTENT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
        "required_entities": ["filename", "content"],
        "transitions": {
            "INIT": [
                {
                    "condition": {
                        "type": "all_of",
                        "predicates": [
                            { "type": "entity_exists", "key": "filename" },
                            { "type": "entity_exists", "key": "content" }
                        ]
                    },
                    "next_state": "READY_FOR_EXECUTION"
                },
                {
                    "condition": { "type": "entity_exists", "key": "filename" },
                    "next_state": "AWAITING_CONTENT"
                }
            ],
            "AWAITING_CONTENT": [
                {
                    "condition": { "type": "entity_exists", "key": "content" },
                    "next_state": "READY_FOR_EXECUTION"
                }
            ]
        },
        "clarification_messages": {
            "filename": "ファイル名を教えていただけますか？",
            "content": "ファイルの内容を教えていただけますか？"
        }
    },
    "FILE_COPY": {
        "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
        "required_entities": ["source_filename", "destination_filename"],
        "transitions": {
            "INIT": [{"condition": {"type": "all_of", "predicates": [{"type": "entity_exists", "key": "source_filename"}, {"type": "entity_exists", "key": "destination_filename"}]}, "next_state": "READY_FOR_EXECUTION"}]
        },
        "clarification_messages": {"source_filename": "コピー元を教えて", "destination_filename": "コピー先を教えて"}
    },
    "FILE_DELETE": {
        "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
        "required_entities": ["filename"],
        "transitions": {
            "INIT": [{"condition": {"type": "entity_exists", "key": "filename"}, "next_state": "READY_FOR_EXECUTION"}]
        },
        "clarification_messages": {"filename": "削除するファイルを教えて"}
    },
    "CMD_RUN": {
        "states": ["INIT", "READY_FOR_EXECUTION", "COMPLETED", "FAILED"],
        "required_entities": ["command"],
        "transitions": {
            "INIT": [{"condition": {"type": "entity_exists", "key": "command"}, "next_state": "READY_FOR_EXECUTION"}]
        },
        "clarification_messages": {"command": "実行するコマンドを教えて"}
    },
    "BACKUP_AND_DELETE": {
        "type": "COMPOUND_TASK",
        "subtasks": [
            {"name": "FILE_COPY", "parameter_mapping": {"source_filename": "source_filename", "destination_filename": "destination_filename"}},
            {"name": "FILE_DELETE", "parameter_mapping": {"filename": "source_filename"}}
        ],
        "required_entities": ["source_filename", "destination_filename"],
        "clarification_messages": {"source_filename": "バックアップ元を教えて", "destination_filename": "バックアップ先を教えて"}
    },
    "CLARIFICATION_RESPONSE": {
        "states": ["INIT", "AGREED", "DISAGREED", "COMPLETED"],
        "required_entities": ["user_response"],
        "transitions": {
            "INIT": [
                {
                    "condition": { "type": "entity_value_is", "key": "user_response", "value": "AGREE" },
                    "next_state": "AGREED"
                },
                {
                    "condition": { "type": "entity_value_is", "key": "user_response", "value": "DISAGREE" },
                    "next_state": "DISAGREED"
                }
            ]
        }
    }
}

def get_test_definitions(**overrides):
    """
    テスト用のタスク定義を取得
    
    Args:
        **overrides: 特定のタスク定義をオーバーライドする場合
        
    Returns:
        dict: テスト用タスク定義
    """
    definitions = COMMON_TASK_DEFINITIONS.copy()
    definitions.update(overrides)
    return definitions