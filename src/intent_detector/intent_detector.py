import json
import os

class IntentDetector:
    def __init__(self, task_manager, corpus_path=None, config_manager=None):
        """
        Initializes the Intent Detector with a corpus of examples.
        """
        self.config_manager = config_manager
        self.corpus_path = corpus_path
        if not self.corpus_path and config_manager:
            self.corpus_path = config_manager.intent_corpus_path
        elif not self.corpus_path:
            self.corpus_path = "resources/intent_corpus.json"
            
        self.task_manager = task_manager
        self.intents = []
        self.vector_engine = None
        self.load_corpus()

    def load_corpus(self):
        """Loads the intent corpus from a JSON file."""
        if os.path.exists(self.corpus_path):
            try:
                with open(self.corpus_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.intents = data.get("intents", [])
            except Exception as e:
                print(f"Error loading intent corpus: {e}")
                self.intents = []

    def set_vector_engine(self, vector_engine):
        """Sets the VectorEngine instance for semantic matching."""
        self.vector_engine = vector_engine

    def prepare_corpus_vectors(self, morph_analyzer):
        """
        Pre-calculates sentence vectors for all examples in the corpus.
        Uses a cache to speed up startup.
        
        Args:
            morph_analyzer (MorphAnalyzer): Instance to tokenize the corpus examples.
        """
        if not self.vector_engine:
            return

        cache_dir = "cache"
        cache_file = os.path.join(cache_dir, "intent_vectors.pkl")
        corpus_mtime = os.path.getmtime(self.corpus_path) if os.path.exists(self.corpus_path) else 0
        
        # Try to load from cache
        import pickle
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    cache_data = pickle.load(f)
                    if cache_data.get("mtime") == corpus_mtime:
                        self.intent_vectors = cache_data.get("vectors", {})
                        # print(f"Loaded {len(self.intent_vectors)} intent vectors from cache.")
                        return
            except Exception as e:
                # print(f"Error loading cache: {e}")
                pass

        # If cache invalid or missing, recalculate
        self.intent_vectors = {}
        for intent in self.intents:
            name = intent.get("name")
            candidates = intent.get("examples", [])
            vectors = []
            for text in candidates:
                # Tokenize
                temp_context = {"original_text": text}
                tokens_data = morph_analyzer.analyze(temp_context).get("analysis", {}).get("tokens", [])
                words = self._extract_content_words(tokens_data)
                
                # Get sentence vector from VectorEngine
                vec = self.vector_engine.get_sentence_vector(words)
                if vec is not None:
                    vectors.append(vec)
            
            self.intent_vectors[name] = vectors
        
        # Save to cache
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump({"mtime": corpus_mtime, "vectors": self.intent_vectors}, f)
        except Exception as e:
            # print(f"Error saving cache: {e}")
            pass

    def _extract_content_words(self, tokens):
        """Filters tokens to keep only content-bearing words."""
        noise_pos = ["助詞", "助動詞", "記号", "接続詞"]
        ext_tokens = {"txt", "md", "csv", "json", "xml", "html", "cs", "config", "log", "yaml", "yml", "csproj", "sln", "slnx"}
        has_extension = False
        for t in tokens:
            base = (t.get("base", t.get("surface", "")) or "").lower()
            if base in ext_tokens:
                has_extension = True
                break
        words = []
        for t in tokens:
            pos_main = t.get("pos", "").split(",")[0]
            if pos_main not in noise_pos:
                word = t.get("base", t.get("surface"))
                if word and word != "*":
                    word_low = str(word).lower()
                    if word_low in ext_tokens:
                        continue
                    if word in [".", "_", "-"]:
                        continue
                    if has_extension and str(word).isascii():
                        continue
                    words.append(word)
        return words

    def add_intent_rule(self, intent_name, pattern, confidence_score, example=None):
        """
        Adds a new example to an existing intent or creates a new one.
        Saves the updated corpus to disk.
        """
        intent_found = False
        for intent in self.intents:
            if intent.get("name") == intent_name:
                # Avoid duplicates
                if pattern and pattern not in intent.get("examples", []):
                    intent.setdefault("examples", []).append(pattern)
                if example and example not in intent.get("examples", []):
                    intent.setdefault("examples", []).append(example)
                intent_found = True
                break
        
        if not intent_found:
            self.intents.append({
                "name": intent_name,
                "examples": [t for t in [pattern, example] if t]
            })

        self.save_corpus()

    def save_corpus(self):
        """Saves the current intents to the corpus JSON file."""
        try:
            with open(self.corpus_path, "w", encoding="utf-8") as f:
                json.dump({"intents": self.intents}, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving intent corpus: {e}")

    def detect(self, context: dict) -> dict:
        """
        Detects the intent of the user input and its confidence, incorporating state-dependent rules.
        Args:
            context (dict): The pipeline context object.
        Returns:
            dict: The updated context with 'analysis.intent' and 'analysis.intent_confidence'.
        """
        context.setdefault("analysis", {})
        context.setdefault("pipeline_history", [])
        
        text = context.get("original_text", "")
        if not text:
            context["analysis"]["intent"] = "GENERAL"
            context["analysis"]["intent_confidence"] = 0.5 # Default low confidence
            return context

        detected_intent = "GENERAL"
        detected_confidence = 0.5 # Default low confidence

        # Get current task context for state-dependent intent detection
        current_task = context.get("task", {})
        task_name = current_task.get("name")
        task_state = current_task.get("state")
        
        # 1. Semantic Match (High Priority)
        # Prioritize AGREE/DISAGREE only when awaiting explicit approval (not missing-entity clarification)
        is_awaiting_conf = current_task and current_task.get("clarification_needed") and current_task.get("clarification_type") == "APPROVAL"
        if not is_awaiting_conf:
             # Double check in active_tasks directly to be sure
             sid = self.task_manager.get_session_id(context)
             if sid in self.task_manager.active_tasks and self.task_manager.active_tasks[sid].get("clarification_needed") and self.task_manager.active_tasks[sid].get("clarification_type") == "APPROVAL":
                  is_awaiting_conf = True
        
        if is_awaiting_conf and self.vector_engine:
            print(f"[DEBUG] Awaiting confirmation for task {current_task.get('name') if current_task else 'unknown'}")

        # 2. Sentence Vector Match (Fallback)
        if hasattr(self, 'intent_vectors') and self.intent_vectors:
            tokens = context.get("analysis", {}).get("tokens", [])
            query_words = self._extract_content_words(tokens)
            query_vec = self.vector_engine.get_sentence_vector(query_words)
            
            if query_vec is not None:
                best_score = 0.0
                best_intent = "GENERAL"
                threshold = 0.60 # Baseline threshold (from design doc, now 0.60)
                
                # Intent Priority logic: Actions should outrank greetings if scores are reasonably high
                action_intents = ["FILE_CREATE", "FILE_READ", "LIST_DIR", "CMD_RUN", "AGREE", "DISAGREE", "APPLY_CODE_FIX", "GENERATE_TESTS"]
                
                for name, vectors in self.intent_vectors.items():
                    # Apply state-dependent boost to best_score for vector matching
                    state_boost = 0.0
                    if task_name == "FILE_CREATE" and task_state == "AWAITING_CONTENT" and name == "PROVIDE_CONTENT":
                        state_boost = 0.1 # Small boost
                
                    # Confirmation Context Boost for Vector Match
                    if is_awaiting_conf and name in ["AGREE", "DISAGREE"]:
                        state_boost = 0.2 # Significant boost during confirmation
                
                    for vec in vectors:
                        score = self.vector_engine.vector_similarity(query_vec, vec)
                        
                        # Boost score for Action intents to prevent false GREETING matches
                        adjusted_score = score
                        if name in action_intents and score > 0.4:
                            adjusted_score += 0.05
                            
                        # High confidence for specific greetings if they're close enough
                        if name == "GREETING" and adjusted_score > 0.8:
                            adjusted_score += 0.1
                        
                        adjusted_score += state_boost # Apply state-dependent boost
                            
                        if adjusted_score > best_score:
                            best_score = adjusted_score
                            best_intent = name
                
                if best_score > threshold:
                    detected_intent = best_intent
                    detected_confidence = best_score # Use vector score as confidence
                
        context["analysis"]["intent"] = detected_intent
        context["analysis"]["intent_confidence"] = detected_confidence
        context["pipeline_history"].append("intent_detector")
        
        return context
