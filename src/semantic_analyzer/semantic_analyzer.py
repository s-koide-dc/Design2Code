# -*- coding: utf-8 -*-
# src/semantic_analyzer/semantic_analyzer.py

import json
import os
import re
import sqlite3
from typing import Optional, List, Dict

from src.utils.text_parser import extract_urls
class SemanticAnalyzer:
    def __init__(self, task_manager, knowledge_file_path=None, config_manager=None, morph_analyzer=None):
        self.task_manager = task_manager
        self.config_manager = config_manager
        self.morph_analyzer = morph_analyzer
        
        # 1. Load Custom Knowledge (templates, specific terms)
        kb_path = knowledge_file_path
        if not kb_path and config_manager:
            kb_path = config_manager.custom_knowledge_path
            
        full_kb = self._load_knowledge_base(kb_path)
        self.custom_knowledge = full_kb.get("knowledge", full_kb)
        
        # 2. Database Connection for Dictionary
        self.db_path = config_manager.dictionary_db_path if config_manager else os.path.join('resources', 'dictionary.db')

    def _get_meaning(self, word: str) -> Optional[str]:
        """Looks up meaning in custom knowledge first, then in dictionary DB."""
        # 1. Check Custom Knowledge (priority)
        kb_entry = self.custom_knowledge.get(word)
        if kb_entry:
            return kb_entry.get("meaning") if isinstance(kb_entry, dict) else kb_entry if isinstance(kb_entry, str) else None
        
        # 2. Check SQLite Dictionary
        if not os.path.exists(self.db_path):
            return None
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT meaning FROM dictionary WHERE word = ?", (word,))
            row = cursor.fetchone()
            conn.close()
            
            return row[0] if row else None
        except Exception:
            return None

    def search_by_meaning(self, query: str, limit: int = 5) -> List[Dict[str, str]]:
        """Searches for words by their meaning using FTS5."""
        if not os.path.exists(self.db_path):
            return []
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # FTS5 MATCH query
            cursor.execute(
                "SELECT word, meaning FROM dictionary_fts WHERE meaning MATCH ? LIMIT ?",
                (query, limit)
            )
            results = [{"word": row[0], "meaning": row[1]} for row in cursor.fetchall()]
            conn.close()
            return results
        except Exception:
            return []

    def _load_knowledge_base(self, filepath: str) -> dict:
        if not filepath:
            return {}
        if not os.path.exists(filepath):
            return {}
            
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
        except Exception:
            return {}

    def analyze(self, context: dict) -> dict:
        context.setdefault("analysis", {})
        context.setdefault("pipeline_history", [])
        context.setdefault("errors", [])

        if "chunks" not in context.get("analysis", {}):
            context["errors"].append({"module": "semantic_analyzer", "message": "分析対象のチャンクが見つかりません。"})
            return context

        chunks = context["analysis"]["chunks"]
        topics = []
        for chunk in chunks:
            for token in chunk:
                pos = token.get("pos", "")
                if pos.startswith("名詞"):
                    text = token.get("base", token.get("surface", ""))
                    if text == "*": text = token.get("surface", "")
                    meaning = self._get_meaning(text)
                    topics.append({"text": text, "pos": pos, "meaning": meaning})
        
        unique_topics = []
        seen = set()
        for t in topics:
            if t["text"] not in seen:
                unique_topics.append(t)
                seen.add(t["text"])
        context["analysis"]["topics"] = unique_topics
        
        history = context.get("history", [])
        text = context.get("original_text", "")
        intent = context["analysis"].get("intent")
        extracted = self._extract_entities(text, history, context, intent)
        
        existing = context["analysis"].get("entities", {})
        existing.update(extracted)
        context["analysis"]["entities"] = existing
        context["pipeline_history"].append("semantic_analyzer")
        return context

    def _extract_entities(self, text: str, history: list, context: dict, intent: str) -> dict:
        extracted = {}
        base_conf = 0.9
        
        current_task = context.get("task", {})
        task_name = current_task.get("name")

        # 1. Patterns for Filenames
        fn_in_quotes = r'[「『"“”](?P<qfn>[^」』"“”]+)[」』"“”]'
        bare_fn = r'(?P<bfn>[\w\-\./\\]+\.[a-zA-Z0-9]{1,10})'
        dotted_name = r'(?P<dn>[a-zA-Z0-9_]+(?:\.[a-zA-Z0-9_]+)+)'
        
        filename_search_text = text
        # Skip filename extraction from the part of text that is clearly content
        explicit_content_match = re.search(r'(?:中身|内容)は\s*([『"「“][^』"」”]+[』"」”])', text)
        if explicit_content_match:
            filename_search_text = text.replace(explicit_content_match.group(1), "")

        # 2. URL Extraction (Highest Priority)
        urls = extract_urls(text)
        if urls:
            url_val = urls[0]
            extracted["url"] = {"value": url_val, "confidence": 1.0}
            # Remove URL from text to avoid misidentifying it as a filename
            filename_search_text = filename_search_text.replace(url_val, "")

        # 3. Filename Extraction (Priority)
        # Single filename match
        # For dotted names, ONLY extract if explicitly marked as "file" or similar.
        # Clear extensions are allowed to be extracted as filenames automatically.
        extensions = r'\.(json|txt|md|csv|xml|html|cs|config|log|pdf|zip|png|jpg)'
        fn_with_ext = rf'(?P<bfn>[\w\-\./\\]+{extensions})'
        
        # We REMOVE {dotted_name} from the automatic extraction to avoid matching code.
        single_fn_pattern = rf'(?:{fn_in_quotes}|(?:(?:名前は|ファイル名が|ファイル)\s*){dotted_name}|{fn_with_ext})'

        if intent in ["FILE_MOVE", "FILE_COPY", "BACKUP_AND_DELETE"]:
            # Source and Destination (e.g., "A を B に移動")
            from src.utils.context_utils import normalize_path
            parts = re.split(r'を|から', filename_search_text)
            if len(parts) >= 2:
                src_part = parts[0]
                dest_part = parts[1]
                
                src_match = re.search(single_fn_pattern, src_part)
                if src_match:
                    try:
                        val = (src_match.groupdict().get('qfn') or 
                               src_match.groupdict().get('dn') or 
                               src_match.groupdict().get('bfn'))
                        if val: extracted["source_filename"] = {"value": normalize_path(val), "confidence": base_conf}
                    except IndexError: pass
                
                dest_match = re.search(single_fn_pattern, dest_part)
                if dest_match:
                    try:
                        val = (dest_match.groupdict().get('qfn') or 
                               dest_match.groupdict().get('dn') or 
                               dest_match.groupdict().get('bfn'))
                        if val: extracted["destination_filename"] = {"value": normalize_path(val), "confidence": base_conf}
                    except IndexError: pass

        if not extracted.get("filename") and not extracted.get("source_filename") and intent not in ["FILE_MOVE", "FILE_COPY", "BACKUP_AND_DELETE"]:
            from src.utils.context_utils import normalize_path
            m = re.search(single_fn_pattern, filename_search_text, re.UNICODE)
            if m:
                try:
                    val = (m.groupdict().get('qfn') or 
                           m.groupdict().get('dn') or 
                           m.groupdict().get('bfn'))
                    if val:
                        val = val.strip()
                        # --- NEW: Guard against keyword-as-filename and URLs ---
                        is_url = "://" in val or val.startswith("http") or val.startswith("www.")
                        if (val in ["ファイル", "クラス"] and re.search(rf"{val}\s*(?:を)?(?:作成|作って|作る|解析|分析|読|表示|削除|消して)", filename_search_text)) or is_url:
                             pass # Don't extract these as names
                        else:
                             extracted["filename"] = {"value": normalize_path(val), "confidence": base_conf}
                except IndexError: pass

        # 3. Content Extraction
        # Look for explicit "内容は..." or "中身は..."
        explicit_content = re.search(r'(?:中身|内容)は\s*[『"「“]([^』"」”]+)[』"」”]', text)
        if explicit_content:
             extracted["content"] = {"value": explicit_content.group(1), "confidence": 0.9}
        elif intent in ["FILE_CREATE", "FILE_APPEND"]:
            # Heuristic: If we already have a filename, and there are other quoted strings, one of them is content.
            all_quoted = re.findall(r'[「『"“”]([^」』"“”]+)[」』"“”]', text)
            filename_val = extracted.get("filename", {}).get("value")
            
            if not explicit_content and all_quoted:
                if filename_val:
                    # Look for a quoted string that is NOT the filename
                    for q in all_quoted:
                        if q not in filename_val:
                            extracted["content"] = {"value": q, "confidence": base_conf}
                            break
                elif len(all_quoted) >= 2:
                    # If no filename identified yet but multiple quotes, assume 1st is filename, 2nd is content
                    from src.utils.context_utils import normalize_path
                    extracted["filename"] = {"value": normalize_path(all_quoted[0]), "confidence": base_conf}
                    extracted["content"] = {"value": all_quoted[1], "confidence": base_conf}

        # 4. Ensure filename doesn't duplicate content (Sanity Check)
        if extracted.get("filename") and extracted.get("content") and extracted["filename"]["value"] == extracted["content"]["value"]:
             # If they are identical, it was likely misidentified. 
             if re.search(rf'[「『"“”]{re.escape(extracted["filename"]["value"])}[」』"“”]\s*(?:を)?(?:作成|作って|作る|追記|追加)', text):
                  del extracted["content"]

        # 5. Aggressive extraction for awaiting states
        if not extracted.get("filename") and not extracted.get("destination_filename") and not extracted.get("source_filename"):
            from src.utils.context_utils import extract_path_from_text
            val = extract_path_from_text(text)
            if val:
                awaiting = context.get("analysis", {}).get("awaiting_entity")
                if awaiting in ["filename", "source_filename", "destination_filename", "project_path"]:
                    extracted[awaiting] = {"value": val, "confidence": 1.0}
                elif task_name == "FILE_MOVE":
                    t_params = current_task.get("parameters", {})
                    if t_params.get("source_filename"):
                        extracted["destination_filename"] = {"value": val, "confidence": base_conf}
                    else:
                        extracted["source_filename"] = {"value": val, "confidence": base_conf}
                else:
                    extracted["filename"] = {"value": val, "confidence": base_conf}

        # 6. Anaphora
        if not (extracted.get("filename") or extracted.get("source_filename")):
            if re.search(r'(それ|そのファイル|さっきの|例のファイル)', text) or intent == "FILE_DELETE":
                res = self._resolve_from_history(history, "filename") or self._resolve_from_history(history, "source_filename")
                if res: extracted["filename"] = res

        # 7. Language and Commands
        lang_match = re.search(r'\b(python|csharp|javascript)\b', text, re.IGNORECASE)
        if lang_match: extracted["language"] = {"value": lang_match.group(1).lower().replace("c#", "csharp"), "confidence": base_conf}
        
        if intent == "CS_TEST_RUN" and not extracted.get("project_path"):
            fn = extracted.get("filename")
            if fn:
                extracted["project_path"] = fn
                del extracted["filename"]
            else:
                res = self._resolve_from_history(history, "project_path") or self._resolve_from_history(history, "filename")
                if res: extracted["project_path"] = res
        
        cmd_match = re.search(r'「([^」]+)」\s*(?:を実行|を動かして)', text)
        if cmd_match: extracted["command"] = {"value": cmd_match.group(1), "confidence": base_conf}

        # 8. Specific Intent Extractions (CS_QUERY_ANALYSIS, MANAGE_KNOWLEDGE, etc.)
        if intent == "CS_QUERY_ANALYSIS":
            query_match = re.search(r'(.+?)(?:の)?(?:要約|詳細|呼び出し元|が呼び出し)', text)
            if query_match:
                target = query_match.group(1).strip()
                extracted["target_name"] = {"value": target, "confidence": base_conf}
                if "要約" in text: extracted["query_type"] = {"value": "class_summary", "confidence": 1.0}
                elif "詳細" in text: extracted["query_type"] = {"value": "method_summary", "confidence": 0.9}
                elif "呼び出し元" in text: extracted["query_type"] = {"value": "called_by", "confidence": 1.0}
                elif "呼び出し" in text: extracted["query_type"] = {"value": "method_calls", "confidence": 1.0}

        if intent == "MANAGE_KNOWLEDGE":
            if re.search(r'(一覧|表示|見せて|状況|データ)', text):
                extracted["operation"] = {"value": "list", "confidence": 1.0}
            search_match = re.search(r'(.+?)(?:に関連する|に関係する|の)?コード(?:を)?(?:検索|探して|見つけて)', text)
            if search_match:
                extracted["operation"] = {"value": "search_code", "confidence": 1.0}
                extracted["query"] = {"value": search_match.group(1).strip(), "confidence": 0.9}

        if intent == "DOC_REFINE" and not extracted.get("filename"):
            doc_match = re.search(r'([\w\./\\]+design\.md)', text)
            if doc_match:
                from src.utils.context_utils import normalize_path
                extracted["filename"] = {"value": normalize_path(doc_match.group(1)), "confidence": 1.0}

        if intent == "REVERSE_DICTIONARY_SEARCH":
            m = re.search(r'(.+?)(?:という|の)?意味(?:を)?持つ(?:言葉|単語|記号)', text)
            if not m: m = re.search(r'(.+?)(?:ような|といった|な)(?:言葉|単語|記号)', text)
            if m: extracted["query"] = {"value": m.group(1).strip(), "confidence": 1.0}

        if intent == "EXECUTE_GOAL_DRIVEN_TDD" or intent == "PROVIDE_CRITERIA":
            ac_match = re.search(r'受け入れ条件は[、\s]*(.+)', text)
            if ac_match: extracted["acceptance_criteria"] = {"value": [ac_match.group(1).strip()], "confidence": 1.0}

        # 9. State-dependent Boost
        task_state = current_task.get("state")
        if task_state:
            for key in extracted:
                if task_state == f"AWAITING_{key.upper()}":
                    extracted[key]["confidence"] = 1.0

        return extracted

    def _resolve_from_history(self, history: list, key: str):
        for entry in reversed(history):
            val = entry.get("entities", {}).get(key)
            if val: return val if isinstance(val, dict) else {"value": val, "confidence": 0.8}
        return None
