import xml.etree.ElementTree as ET
import csv
import json
import os
import sys
import sqlite3

# Mapping from JMdict entities to simplified POS tags for Janome
POS_MAP = {
    "n": "名詞",
    "v1": "動詞-一段",
    "v5k": "動詞-五段-カ行",
    "v5s": "動詞-五段-サ行",
    "v5t": "動詞-五段-タ行",
    "v5n": "動詞-五段-ナ行",
    "v5m": "動詞-五段-マ行",
    "v5r": "動詞-五段-ラ行",
    "v5w": "動詞-五段-ワ行",
    "v5g": "動詞-五段-ガ行",
    "v5b": "動詞-五段-バ行",
    "adj-i": "形容詞",
    "adj-na": "名詞-形容動詞語幹",
    "adv": "副詞",
    "vx": "動詞",
    "vi": "動詞-自動詞",
    "vt": "動詞-他動詞",
    "prt": "助詞",
    "aux": "助動詞",
    "conj": "接続詞",
    "int": "感動詞"
}

def parse_jmdict():
    xml_path = os.path.join(os.getcwd(), 'resources', 'JMdict_e.xml')
    output_db = os.path.join(os.getcwd(), 'resources', 'dictionary.db')
    
    if not os.path.exists(xml_path):
        print(f"Error: {xml_path} not found. Run fetch_jmdict.py first.")
        return

    print(f"Parsing {xml_path} and updating {output_db}...")
    
    # SQLite Setup
    if os.path.exists(output_db):
        os.remove(output_db)
    
    conn = sqlite3.connect(output_db)
    cursor = conn.cursor()
    # Main table
    cursor.execute('''
        CREATE TABLE dictionary (
            word TEXT PRIMARY KEY,
            meaning TEXT,
            pos TEXT,
            reading TEXT
        )
    ''')
    # Full Text Search table for meanings
    cursor.execute('CREATE VIRTUAL TABLE dictionary_fts USING fts5(word, meaning)')

    # Iterative parsing to handle large XML
    context = ET.iterparse(xml_path, events=("end",))
    
    db_entries = []
    
    count = 0
    
    for event, elem in context:
        if elem.tag == "entry":
            k_eles = [e.text for e in elem.findall("./k_ele/keb")]
            r_eles = [e.text for e in elem.findall("./r_ele/reb")]
            
            if k_eles:
                surface_forms = k_eles
                reading_form = r_eles[0] if r_eles else ""
            else:
                surface_forms = r_eles
                reading_form = r_eles[0] if r_eles else ""
            
            sense = elem.find("./sense")
            if sense is not None:
                pos_tags = [e.text for e in sense.findall("./pos")]
                main_pos = "名詞"
                for tag in pos_tags:
                    tag_clean = tag.strip()
                    if tag_clean in POS_MAP:
                        main_pos = POS_MAP[tag_clean]
                        break
                
                glosses = [e.text for e in sense.findall("./gloss")]
                meaning = "; ".join(glosses)
                
                for surface in surface_forms:
                    if not surface: continue
                    
                    reading_clean = reading_form.replace(',', '')
                    db_entries.append((surface, meaning, main_pos, reading_clean))
            
            elem.clear()
            count += 1
            if count % 10000 == 0:
                print(f"Processed {count} entries...")
                # Intermediate commit to save memory if needed, but here we'll just insert in chunks
                cursor.executemany('INSERT OR REPLACE INTO dictionary VALUES (?, ?, ?, ?)', db_entries)
                cursor.executemany('INSERT INTO dictionary_fts VALUES (?, ?)', [(e[0], e[1]) for e in db_entries])
                db_entries = []

    # Final insert
    if db_entries:
        cursor.executemany('INSERT OR REPLACE INTO dictionary VALUES (?, ?, ?, ?)', db_entries)
        cursor.executemany('INSERT INTO dictionary_fts VALUES (?, ?)', [(e[0], e[1]) for e in db_entries])

    print(f"Finished parsing {count} entries.")
    
    conn.commit()
    conn.close()
    print("Success. Dictionary DB updated.")

if __name__ == "__main__":
    parse_jmdict()

if __name__ == "__main__":
    parse_jmdict()
