import json
import os

OUTPUT_KB_PATH = os.path.join(os.getcwd(), 'resources', 'custom_knowledge.json')
DB_PATH = os.path.join(os.getcwd(), 'resources', 'dictionary.db')

def build_knowledge_base():
    """
    Maintains the custom_knowledge.json skeleton.
    Dictionary data is now handled separately via SQLite (dictionary.db).
    """
    print("Custom Knowledge Base Maintenance")
    print("-" * 30)
    
    if not os.path.exists(DB_PATH):
        print(f"WARNING: {DB_PATH} not found. Run parse_jmdict.py to build the dictionary database.")

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
            print(f"Loading existing {OUTPUT_KB_PATH}...")
            with open(OUTPUT_KB_PATH, 'r', encoding='utf-8') as f:
                existing_kb = json.load(f)
                # Merge existing data into our template
                for key in curated_knowledge:
                    if key in existing_kb:
                        curated_knowledge[key].update(existing_kb[key])
        except Exception as e:
            print(f"Error loading existing custom_knowledge.json: {e}")

    # Ensure critical terms are present if not already
    critical_terms = {
        "エージェント": {"meaning": "ユーザーの代わりに特定のタスクやアクションを実行するソフトウェア。"},
        "クラス": {"meaning": "class。オブジェクト指向プログラミングにおける設計図。"}
    }
    
    for term, data in critical_terms.items():
        if term not in curated_knowledge["knowledge"]:
            print(f"Adding critical term: {term}")
            curated_knowledge["knowledge"][term] = data

    try:
        # Save the updated custom_knowledge.json
        with open(OUTPUT_KB_PATH, 'w', encoding='utf-8') as f:
            json.dump(curated_knowledge, f, ensure_ascii=False, indent=2)
        print(f"Successfully maintained custom knowledge base at {OUTPUT_KB_PATH}")
        print(f"Custom terms count: {len(curated_knowledge['knowledge'])}")

    except Exception as e:
        print(f"An unexpected error occurred while saving: {e}")

if __name__ == '__main__':
    build_knowledge_base()