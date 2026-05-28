import json
import os
import sys

sys.path.append(os.getcwd())

from src.utils.cli_output import emit_error, emit_progress

OUTPUT_KB_PATH = os.path.join(os.getcwd(), 'resources', 'custom_knowledge.json')
DB_PATH = os.path.join(os.getcwd(), 'resources', 'dictionary.db')

def build_knowledge_base():
    """
    Maintains the custom_knowledge.json skeleton.
    Dictionary data is now handled separately via SQLite (dictionary.db).
    """
    emit_progress("Custom Knowledge Base Maintenance")
    emit_progress("-" * 30)
    
    if not os.path.exists(DB_PATH):
        emit_error(f"警告: 辞書 DB が見つかりません: {DB_PATH}")
        emit_error("先に parse_jmdict.py を実行して dictionary.db を作成してください。")

    curated_knowledge = {
        "knowledge": {}, 
        "default_responses": {
            "general_unknown": "ごめんなさい、よく分かりません。",
            "unknown_topic": "そのトピック「{topic}」については今勉強中です！もっと詳しくなったら教えてくださいね。"
        },
        "concept_responses": {},
        "intent_responses": {}
    }

    # Load existing custom knowledge to preserve manual edits
    if os.path.exists(OUTPUT_KB_PATH):
        try:
            emit_progress(f"Loading existing {OUTPUT_KB_PATH}...")
            with open(OUTPUT_KB_PATH, 'r', encoding='utf-8') as f:
                existing_kb = json.load(f)
                # Merge existing data into our template
                for key in curated_knowledge:
                    if key in existing_kb:
                        curated_knowledge[key].update(existing_kb[key])
        except Exception as e:
            emit_error(f"エラー: 既存の custom_knowledge.json の読込に失敗しました: {e}")

    # Ensure critical terms are present if not already
    critical_terms = {
        "エージェント": {"meaning": "ユーザーの代わりに特定のタスクやアクションを実行するソフトウェア。"},
        "クラス": {"meaning": "class。オブジェクト指向プログラミングにおける設計図。"}
    }
    
    for term, data in critical_terms.items():
        if term not in curated_knowledge["knowledge"]:
            emit_progress(f"Adding critical term: {term}")
            curated_knowledge["knowledge"][term] = data

    try:
        # Save the updated custom_knowledge.json
        with open(OUTPUT_KB_PATH, 'w', encoding='utf-8') as f:
            json.dump(curated_knowledge, f, ensure_ascii=False, indent=2)
        emit_progress(f"Successfully maintained custom knowledge base at {OUTPUT_KB_PATH}")
        emit_progress(f"Custom terms count: {len(curated_knowledge['knowledge'])}")
        return 0

    except Exception as e:
        emit_error(f"エラー: custom knowledge base の保存に失敗しました: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(build_knowledge_base())
