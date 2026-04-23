import json
import os
import random
import datetime

class ResponseGenerator:
    def __init__(self, vector_engine=None, log_manager=None, task_manager=None):
        """
        Initializes the Response Generator.
        
        Args:
            vector_engine: Optional VectorEngine instance for similarity calculation.
            log_manager: Optional LogManager instance.
            task_manager: Optional TaskManager instance to share task definitions.
        """
        kb = self._load_knowledge_base()
        self.knowledge = kb.get("knowledge", {})
        self.default_responses = kb.get("default_responses", {})
        self.default_response = self.default_responses.get("general_unknown", "ごめんなさい、よく分かりません。")
        self.intent_responses = kb.get("intent_responses", {})
        
        # Explicitly remove CAPABILITY from intent_responses loaded from knowledge_base.json
        # to ensure the hardcoded CAPABILITY response in generate() takes precedence.
        if "CAPABILITY" in self.intent_responses:
            del self.intent_responses["CAPABILITY"]

        self.concept_responses = kb.get("concept_responses", {})
        self.vector_engine = vector_engine
        self.log_manager = log_manager
        self.task_manager = task_manager
        
        # Load local definitions only if no task_manager is provided
        self._local_task_definitions = None
        if not self.task_manager:
            self._local_task_definitions = self._load_task_definitions()

    @property
    def task_definitions(self) -> dict:
        """Retrieve task definitions dynamically from task_manager if available."""
        if self.task_manager and hasattr(self.task_manager, 'task_definitions'):
            return self.task_manager.task_definitions
        if self._local_task_definitions is None:
            self._local_task_definitions = self._load_task_definitions()
        return self._local_task_definitions

    def _load_task_definitions(self) -> dict:
        """Loads the task definitions from a JSON file."""
        filepath = "resources/task_definitions.json"
        if not os.path.exists(filepath):
            return {}
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading task definitions: {e}")
            return {}

    def _load_knowledge_base(self) -> dict:
        """Loads the knowledge base from a JSON file."""
        # Try custom_knowledge.json first, then fallback to knowledge_base.json
        for filename in ["custom_knowledge.json", "knowledge_base.json"]:
            filepath = os.path.join(os.getcwd(), 'resources', filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"Error loading {filename}: {e}")
        return {}

    def generate(self, context: dict) -> dict:
        """
        Generates a response based on extracted topics and related concepts.
        """
        context.setdefault("analysis", {})
        context.setdefault("pipeline_history", [])
        context.setdefault("errors", [])

        # --- NEW: Check for Safety Policy Errors early ---
        safety_errors = [e["message"] for e in context.get("errors", []) if "Safety Policy Error" in e.get("message", "")]
        if safety_errors:
            return self._finalize_response(context, f"エラーが発生しました: {safety_errors[0]}")
        # ------------------------------------------------

        topics_data = context.get("analysis", {}).get("topics", [])

        intent = context.get("analysis", {}).get("intent", "GENERAL")
        response_text = None

        # --- Stage 1: Specific Intent Checks (that don't strictly require topics) ---
        if intent in self.intent_responses:
            options = self.intent_responses[intent]
            if isinstance(options, list):
                response_text = random.choice(options)
            else:
                response_text = options
        elif intent == "TIME":
            now = datetime.datetime.now()
            response_text = f"現在の時刻は {now.strftime('%H時%M分')} です。"
        elif intent == "CAPABILITY":
            response_text = "私はAIアシスタントです。ファイル操作やコードの解析、タスク管理を支援できます。"
        # Add other simple conversational intents here as needed

        # If a response was generated in Stage 1, finalize and return
        if response_text is not None:
            return self._finalize_response(context, response_text)

        # --- Stage 2: Topic-based Response Generation (requires topics) ---
        # If topics are missing and intent is not definition, we might not have enough info
        if not topics_data:
            if intent == "DEFINITION": # DEFINITION intent absolutely needs topics
                context["errors"].append({
                    "module": "response_generator",
                    "message": "応答を生成するためのトピックがありません。意味解析が先に行われている必要があります。"
                })
                context['response'] = {'text': self.default_response}
                return context
            # For other intents where topics are not strictly required, allow to proceed to default fallback
            # This handles cases like GENERAL intent not having topics but still getting default response

        # 2.1. High-priority Concept Vector Check (requires topics_data)
        if self.vector_engine and self.vector_engine.is_ready and topics_data:
            concepts = list(self.concept_responses.keys())
            words_to_check = [t.get('lemma') or t.get('text') for t in topics_data if isinstance(t, dict)]
            
            query_vec = self.vector_engine.get_sentence_vector(words_to_check)
            if query_vec is not None:
                matches = []
                for concept in concepts:
                    concept_vec = self.vector_engine.get_sentence_vector([concept])
                    if concept_vec is not None:
                        score = self.vector_engine.vector_similarity(query_vec, concept_vec)
                        if concept == "天気" and "天気" in words_to_check: # Special handling for weather concept
                             score += 0.1
                        matches.append((concept, score))
                
                if matches:
                    best_match, score = max(matches, key=lambda x: x[1])
                    if score > 0.4: # Threshold for concept matching
                        response_text = self.concept_responses[best_match]

        # 2.2. Definition Intent Handling (requires topics_data and if not already handled)
        if response_text is None and intent == "DEFINITION" and topics_data:
            key_term = None
            tokens = context.get("analysis", {}).get("tokens", [])

            # Strategy: Find the longest noun sequence before a definition particle ("は", "と", "とは")
            definition_particle_idx = -1
            for i, token in enumerate(tokens):
                surface = token.get("surface", "")
                if surface == "は" or "とは" in surface:
                    definition_particle_idx = i
                    break
            
            if definition_particle_idx != -1:
                longest_noun_sequence = ""
                current_noun_sequence = ""
                # Scan tokens before the definition particle
                for i in range(definition_particle_idx):
                    token = tokens[i]
                    pos = token.get("pos", "")
                    if pos.startswith("名詞"):
                        current_noun_sequence += token.get("surface")
                    else:
                        if len(current_noun_sequence) > len(longest_noun_sequence):
                            longest_noun_sequence = current_noun_sequence
                        current_noun_sequence = ""
                
                # Check for any remaining sequence after the loop
                if len(current_noun_sequence) > len(longest_noun_sequence):
                    longest_noun_sequence = current_noun_sequence
                
                if longest_noun_sequence:
                    key_term = longest_noun_sequence
            
            # Fallback: if no clear noun phrase before particle, just use the first noun in topics
            if not key_term:
                for topic in topics_data:
                    if topic.get("pos", "").startswith("名詞"):
                        key_term = topic.get("text")
                        break
            
            # Now, find the meaning for the identified key_term
            if key_term:
                found_meaning = False
                # Try to find meaning for the exact final_key_term in topics
                for topic in topics_data:
                    if topic.get("text") == key_term and topic.get("meaning"):
                        response_text = f"「{key_term}」ですね。辞書によると「{topic.get('meaning')}」という意味です。"
                        found_meaning = True
                        break
                
                # If exact match for meaning not found for key_term, assume not found.
                if not found_meaning:
                    response_text = f"申し訳ありません。「{key_term}」の意味は辞書に見つかりませんでした。"
            else:
                response_text = "申し訳ありません。どの言葉について説明すればよいか分かりませんでした。"

        # 2.3. Fallback to General Template Logic (requires topics_data)
        if response_text is None and topics_data:
            topic_strings = [t.get('text', '') for t in topics_data if isinstance(t, dict)]
            primary_topic = None
            found_concept = None
            for topic_val in topic_strings: # Renamed 'topic' to 'topic_val'
                if topic_val in self.knowledge:
                    kb_entry = self.knowledge[topic_val]
                    if isinstance(kb_entry, dict) and kb_entry.get("related"):
                        primary_topic = topic_val
                        for concept in kb_entry.get("related", []):
                            if concept in topic_strings:
                                found_concept = concept
                                break
                        if found_concept: break
            
            if primary_topic and found_concept:
                template = self.knowledge[primary_topic].get("response_template", "")
                if template:
                    context_topics = "と".join([t for t in topic_strings if t != found_concept])
                    response_text = template.format(topics=context_topics, concept=found_concept)
            elif primary_topic:
                 unknown_template = self.default_responses.get("unknown_topic", "そのトピックについては今勉強中です！もっと詳しくなったら教えてくださいね。")
                 response_text = unknown_template.format(topic=primary_topic)

        # Use default if absolutely no response was generated
        if response_text is None:
            response_text = self.default_response

        # --- Final Assembly ---
        return self._finalize_response(context, response_text)

    def _finalize_response(self, context, response_text):
        """Helper method to finalize the response context."""
        final_response_text = response_text
        action_result = context.get("action_result", {})
        
        # Use intent from analysis or the current task name
        intent = context.get("analysis", {}).get("intent")
        task_info = context.get("task", {})
        task_name = task_info.get("name")

        if not intent and task_name:
            intent = task_name

        if action_result.get("status") in ["success", "error"]:
            action_msg = action_result.get("message", "")
            
            # --- NEW: Specific visualization for Impact Scope ---
            if intent == "CS_IMPACT_SCOPE" and action_result.get("status") == "success":
                impacted = action_result.get("impacted_methods", [])
                target = action_result.get("target_name", "Target")
                if impacted:
                    mermaid = ["graph TD"]
                    # ターゲットノードを目立たせる
                    mermaid.append(f"  T[\"{target}\"]:::target")
                    for m in impacted:
                        # 循環参照や自己参照を避けつつ、ターゲットから影響先へ矢印
                        if m != target:
                            mermaid.append(f"  T --> \"{m}\"")
                    
                    mermaid.append("  classDef target fill:#f96,stroke:#333,stroke-width:4px;")
                    
                    action_msg += "\n\n【影響範囲グラフ】\n```mermaid\n" + "\n".join(mermaid) + "\n```"
            # --------------------------------------------------

            # Special handling for C# Analysis results to make them more readable
            if (intent == "CS_ANALYZE" or task_name == "CS_ANALYZE") and \
               action_result.get("status") == "success" and "analysis" in action_result:
                
                analysis = action_result["analysis"]
                metrics = analysis.get("project_metrics", {})
                objects = analysis.get("manifest", {}).get("objects", [])
                
                summary = []
                summary.append(f"C#プロジェクトの解析が完了しました。")
                summary.append(f"・抽出されたオブジェクト数: {len(objects)} 個 (クラス、レコード、構造体など)")
                
                if metrics:
                    summary.append(f"・総コード行数: {metrics.get('totalLineCount', 0)} 行")
                    summary.append(f"・平均サイクロマティック複雑度: {metrics.get('averageCyclomaticComplexity', 0):.2f}")
                    
                    max_cc = metrics.get('maxCyclomaticComplexity', 0)
                    if max_cc > 10:
                        summary.append(f"⚠️ 注意: 最大複雑度が {max_cc} と高くなっています。リファクタリングの検討をお勧めします。")
                
                summary.append("\n【次にできること】")
                summary.append("1. 「コードのリファクタリング分析をして」")
                summary.append("2. 「C#のテストを実行して」")
                summary.append("3. 「(クラス名) の要約を教えて」")
                
                action_msg = "\n".join(summary)
            
            # Special handling for completed compound tasks
            elif task_info.get("state") == "COMPLETED" and task_info.get("type") == "COMPOUND_TASK":
                action_msg = "完了しました。"

            if action_msg:
                # Add info about generated files if available (e.g., for GENERATE_TESTS)
                if intent == "GENERATE_TESTS" and action_result.get("status") == "success":
                    gen_files = action_result.get("generated_files", [])
                    if gen_files:
                        rel_paths = [os.path.relpath(p, os.getcwd()) for p in gen_files]
                        action_msg += f"\n\n保存先: {', '.join(rel_paths)}"

                # If the initial response was just a default or placeholder, use the action message as the primary response
                if response_text == self.default_response or response_text is None:
                    final_response_text = action_msg
                else:
                    final_response_text = f"{response_text}\n\n{action_msg}"
        
        context["response"] = {"text": final_response_text}
        
        # --- NEW: Append task resumption message for interruptions ---
        if context.get("task_interruption") and context.get("task", {}).get("clarification_message"):
            resumption_msg = context["task"]["clarification_message"]
            if resumption_msg not in final_response_text:
                context["response"]["text"] = f"{final_response_text} {resumption_msg}"
        # -------------------------------------------------------------

        context["pipeline_history"].append("response_generator")
        return context

    def _get_entity_value(self, entity_data, default_value):
        if isinstance(entity_data, dict) and "value" in entity_data:
            return entity_data["value"]
        elif isinstance(entity_data, str):
            return entity_data
        return default_value

    def generate_confirmation_message(self, context: dict) -> dict:
        """
        Generates a user-facing confirmation message for soft block actions.
        Args:
            context (dict): The context object containing the plan and/or task info for approval.
        Returns:
            dict: The updated context object with the confirmation message in context["response"]["text"].
        """
        task_info = context.get("task", {})
        clarification_msg_type = task_info.get("clarification_message")

        action_description = ""
        confirmation_message = ""

        # --- Handle Compound Task Approval Requests ---
        if clarification_msg_type == "COMPOUND_TASK_OVERALL_APPROVAL":
            compound_task_name = task_info.get("name", "複合タスク")
            
            # 1. Try to get template from task definitions
            task_def = self.task_definitions.get(compound_task_name, {})
            templates = task_def.get("templates", {})
            overall_template = templates.get("overall_approval")

            if overall_template:
                task_params = task_info.get("parameters", {})
                flat_params = {}
                for k, v in task_params.items():
                    flat_params[k] = self._get_entity_value(v, "")
                
                try:
                    confirmation_message = overall_template.format(**flat_params)
                    context["response"] = {"text": confirmation_message}
                    context["pipeline_history"].append("response_generator_confirmation")
                    context["pipeline_history"].append("soft_block_confirmation")
                    return context
                except KeyError:
                    pass # Fallback to default generation

            subtasks = task_info.get("subtasks", [])
            
            if subtasks:
                first_subtask = subtasks[0]
                first_subtask_name = first_subtask.get("name", "不明なサブタスク")
                # 最初のサブタスクの詳細パラメータを取得
                first_subtask_params = first_subtask.get("parameters", {})
                if first_subtask.get("action_method") == "_copy_file":
                    source = self._get_entity_value(first_subtask_params.get("source_filename"), "ファイル")
                    dest = self._get_entity_value(first_subtask_params.get("destination_filename"), "バックアップ先")
                    action_description = f"複合タスク「{compound_task_name}」を開始します。まず、ファイル '{source}' を '{dest}' にコピーします。"
                elif first_subtask.get("action_method") == "_delete_file":
                    filename = self._get_entity_value(first_subtask_params.get("filename"), "ファイル")
                    action_description = f"複合タスク「{compound_task_name}」を開始します。まず、ファイル '{filename}' を削除します。"
                else:
                    action_description = f"複合タスク「{compound_task_name}」を開始します。最初のステップは「{first_subtask_name}」です。"
            else:
                action_description = f"複合タスク「{compound_task_name}」を開始します。"
            
            # If we reached here, we have an action_description but no complete message yet.
            # We'll let the common suffix logic at the end handle it.
                
        elif clarification_msg_type == "COMPOUND_TASK_SUBTASK_APPROVAL":
            compound_task_name = task_info.get("name", "複合タスク")
            subtasks = task_info.get("subtasks", [])
            current_subtask_index = task_info.get("current_subtask_index", 0)
            
            if current_subtask_index < len(subtasks):
                active_subtask = subtasks[current_subtask_index]
                subtask_name = active_subtask.get("name", "不明なサブタスク")
                subtask_params = active_subtask.get("parameters", {})
                
                # サブタスクの種類に応じた詳細メッセージ生成
                if active_subtask.get("action_method") == "_delete_file":
                    filename = self._get_entity_value(subtask_params.get("filename"), "ファイル")
                    action_description = f"複合タスク「{compound_task_name}」の次のステップで、ファイル '{filename}' を削除します。"
                elif active_subtask.get("action_method") == "_run_command":
                    command = self._get_entity_value(subtask_params.get("command"), "コマンド")
                    action_description = f"複合タスク「{compound_task_name}」の次のステップで、コマンド '{command}' を実行します。"
                elif active_subtask.get("action_method") == "_copy_file":
                    source = self._get_entity_value(subtask_params.get("source_filename"), "コピー元")
                    dest = self._get_entity_value(subtask_params.get("destination_filename"), "コピー先")
                    action_description = f"複合タスク「{compound_task_name}」の次のステップで、ファイル '{source}' を '{dest}' にコピーします。"
                else:
                    action_description = f"複合タスク「{compound_task_name}」の次のステップ：サブタスク「{subtask_name}」を実行します。"
            else:
                action_description = f"複合タスク「{compound_task_name}」の次のステップを実行します。"
        # --- End Handle Compound Task Approval Requests ---
        
        # --- Existing Plan Confirmation Logic ---
        # If no compound task approval, fall back to plan-based confirmation (for simple tasks or overall compound task plan if plan exists)
        if not action_description: # If not handled by compound task approval
            plan = context.get("plan", {})
            action_method = plan.get("action_method", "不明な操作")
            parameters = plan.get("parameters", {})
            parent_task_name = plan.get("parent_task")

            # This part remains mostly the same as existing logic
            # Prioritize the parent task name for the confirmation message
            # 1. Try to get template from task definitions for parent task
            if parent_task_name:
                task_def = self.task_definitions.get(parent_task_name, {})
                templates = task_def.get("templates", {})
                overall_template = templates.get("overall_approval")
                if overall_template:
                    flat_params = {}
                    for k, v in parameters.items():
                        flat_params[k] = self._get_entity_value(v, "")
                    try:
                        confirmation_message = overall_template.format(**flat_params)
                        context["response"] = {"text": confirmation_message}
                        context["pipeline_history"].append("response_generator_confirmation")
                        context["pipeline_history"].append("soft_block_confirmation")
                        return context
                    except KeyError:
                        pass

            if action_method == "_create_file":
                filename_data = parameters.get("filename")
                filename = self._get_entity_value(filename_data, "ファイル")
                action_description = f"ファイル '{filename}' を作成"
            elif action_method == "_read_file":
                filename_data = parameters.get("filename")
                filename = self._get_entity_value(filename_data, "ファイル")
                action_description = f"ファイル '{filename}' を読み込み"
            elif action_method == "_append_file":
                filename_data = parameters.get("filename")
                filename = self._get_entity_value(filename_data, "ファイル")
                action_description = f"ファイル '{filename}' に追記"
            elif action_method == "_delete_file":
                filename_data = parameters.get("filename")
                filename = self._get_entity_value(filename_data, "ファイル")
                action_description = f"ファイル '{filename}' を削除"
            elif action_method == "_copy_file":
                source_filename_data = parameters.get("source_filename")
                destination_filename_data = parameters.get("destination_filename")
                source_filename = self._get_entity_value(source_filename_data, "コピー元ファイル")
                destination_filename = self._get_entity_value(destination_filename_data, "コピー先ファイル")
                action_description = f"ファイル '{source_filename}' を '{destination_filename}' にコピー"
            elif action_method == "_move_file":
                source_filename_data = parameters.get("source_filename")
                destination_filename_data = parameters.get("destination_filename")
                source_filename = self._get_entity_value(source_filename_data, "移動元ファイル")
                destination_filename = self._get_entity_value(destination_filename_data, "移動先ファイル")
                action_description = f"ファイル '{source_filename}' を '{destination_filename}' に移動"
            elif action_method == "_run_command":
                command_data = parameters.get("command")
                command = self._get_entity_value(command_data, "コマンド")
                action_description = f"コマンド '{command}' を実行"
            elif action_method == "_list_dir":
                directory_data = parameters.get("directory")
                directory = self._get_entity_value(directory_data, "ディレクトリ")
                action_description = f"ディレクトリ '{directory}' の内容を一覧表示"
            elif action_method == "_execute_goal_driven_tdd":
                goal = self._get_entity_value(parameters.get("goal_description"), "機能")
                action_description = f"「{goal}」の実装を開始"
            else:
                action_description = f"不明な操作 ({action_method})"

        if action_description.endswith("します。") or action_description.endswith("です。"):
            confirmation_message = f"{action_description}よろしいですか？"
        elif action_description.endswith("します"):
             confirmation_message = f"{action_description}。よろしいですか？"
        else:
            confirmation_message = f"{action_description}します。よろしいですか？"
            
        context["response"] = {"text": confirmation_message}
        context["pipeline_history"].append("response_generator_confirmation")
        context["pipeline_history"].append("soft_block_confirmation")
        
        return context
