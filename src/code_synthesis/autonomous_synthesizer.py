# -*- coding: utf-8 -*-
import logging
import os
from typing import Dict, List, Any
from .code_synthesizer import CodeSynthesizer
from src.code_verification.compilation_verifier import CompilationVerifier
from src.code_verification.execution_verifier import ExecutionVerifier
from src.advanced_tdd.failure_analyzer import TestFailureAnalyzer
from src.advanced_tdd.models import TDDGoal
# IntentDetector usage is disabled to avoid heuristic intent inference in runtime.
from src.syntactic_analyzer.syntactic_analyzer import SyntacticAnalyzer
from src.semantic_analyzer.semantic_analyzer import SemanticAnalyzer
from src.utils.logic_auditor import LogicAuditor
from src.autonomous_learning.structural_memory import StructuralMemory
import re
import textwrap
import tempfile
import shutil
import os
import time

class AutonomousSynthesizer:
    """合成・検証・自己修復のループを統括するクラス"""

    def __init__(self, config_manager, morph_analyzer=None, vector_engine=None, task_manager=None, method_store=None):
        self.config_manager = config_manager
        self.synthesizer = CodeSynthesizer(config_manager, method_store=method_store, morph_analyzer=morph_analyzer)
        self.verifier = CompilationVerifier(config_manager)
        self.executor = ExecutionVerifier(config_manager)
        self.analyzer = TestFailureAnalyzer({"config": {}, "config_manager": config_manager}) # config_managerを渡す
        self.logger = logging.getLogger(__name__)

        # StructuralMemory (プロジェクト構造の記憶)
        storage_dir = getattr(config_manager, "storage_dir", os.path.join(config_manager.workspace_root, "resources", "vectors", "vector_db"))
        self.structural_memory = StructuralMemory(storage_dir, config_manager, vector_engine, morph_analyzer)

        # 高度な意図解析モジュールの統合
        class DummyTaskManager:
            def __init__(self):
                self.active_tasks = {}
            def get_session_id(self, context=None): return "autonomous_session"
            
        self.task_manager = task_manager or DummyTaskManager()
        from .dependency_resolver import DependencyResolver
        self.dependency_resolver = DependencyResolver(config_manager, structural_memory=self.structural_memory)
        self.intent_detector = None
            
        self.syntactic_analyzer = SyntacticAnalyzer()
        self.semantic_analyzer = SemanticAnalyzer(self.task_manager, config_manager=config_manager)
        self.logic_auditor = LogicAuditor(
            vector_engine=vector_engine,
            morph_analyzer=morph_analyzer,
            knowledge_base=getattr(self.synthesizer, "ukb", None)
        )

    def synthesize_safely(self, method_name: str, design_steps: List[str], max_retries: int = 3, execute: bool = False, session_context: Dict[str, Any] = None, return_type: str = None, input_param_type: str = None, work_dir: str = None, intent: str = None) -> Dict[str, Any]:
        """ビルド（および任意で実行）が成功するまで、負のフィードバックを糧に再試行を繰り返す"""
        session_context = session_context or {}
        
        attempt = 0
        v_res = {}
        result = {}
        
        # Track already resolved packages to avoid loops
        resolved_symbols = set()
        session_dependencies = set()
        
        while attempt <= max_retries:
            attempt += 1
            print(f"\n[AutonomousSynthesizer] Attempt {attempt} for '{method_name}'")
            
            # 1. 合成 (セッションコンテキストを考慮)
            enhanced_steps = design_steps.copy()
            if session_context.get("last_method"):
                last_m = session_context["last_method"]
                ret_type = input_param_type or last_m.get("return_type", "dynamic")
                enhanced_steps.insert(0, f"直前の処理 {last_m['name']} が返した {ret_type} 型のデータを受け取る")
            
            result = self.synthesizer.synthesize(method_name, enhanced_steps, return_type=return_type, input_type_hint=input_param_type, pre_resolved_dependencies=list(session_dependencies), intent=intent)
            code = result["code"]
            
            # 2. 検証 (ビルド)
            print("[AutonomousSynthesizer] Verifying build...")
            v_start = time.time()
            
            # Use current dependencies from path
            current_deps = [{"name": d} for d in result.get("dependencies", [])]
            # 更新された依存関係をセッションレベルで保持
            for d in result.get("dependencies", []): session_dependencies.add(d)
            v_res = self.verifier.verify(code, work_dir=work_dir, dependencies=current_deps)
            v_time = time.time() - v_start
            print(f"[AutonomousSynthesizer] Build took {v_time:.2f}s")
            
            if v_res.get("valid"):
                print("[AutonomousSynthesizer] Build SUCCESS!")
                # Persist the newly resolved packages
                self.dependency_resolver.save_mappings()
                
                # 3. 実行検証 (オプション)
                if execute:
                    print("[AutonomousSynthesizer] Extracting logic goals for assertions...")
                    assertion_goals = self.logic_auditor.extract_assertion_goals(enhanced_steps)
                    
                    print("[AutonomousSynthesizer] Executing code with assertions...")
                    e_start = time.time()
                    e_res = self.executor.run_and_capture(code, method_name, work_dir=work_dir, assertion_goals=assertion_goals, dependencies=current_deps)
                    e_time = time.time() - e_start
                    print(f"[AutonomousSynthesizer] Execution took {e_time:.2f}s")
                    if e_res.get("success"):
                        print("[AutonomousSynthesizer] Execution SUCCESS!")
                        
                        # --- NEW: Positive Semantic Feedback ---
                        if intent:
                            used_ids = result.get("used_ids", [])
                            for uid in used_ids:
                                self.synthesizer.method_store.record_semantic_feedback(uid, intent, is_success=True)
                            if used_ids:
                                print(f"[AutonomousSynthesizer] Positive feedback recorded for {len(used_ids)} methods under intent {intent}")
                        # ---------------------------------------

                        return {
                            "status": "success",
                            "code": code,
                            "attempts": attempt,
                            "has_side_effects": result.get("has_side_effects"),
                            "poco_info": result.get("poco_info")
                        }
                    else:
                        print(f"[AutonomousSynthesizer] Execution FAILED: {e_res.get('exception', {}).get('type')}")
                        
                        # --- NEW: Semantic Feedback Analysis ---
                        from src.advanced_tdd.models import TestFailure
                        test_failure = TestFailure(
                            test_file="runtime_check", test_method=method_name,
                            error_type=e_res.get('exception', {}).get('type', 'RuntimeError'),
                            error_message=e_res.get('exception', {}).get('message', ''),
                            stack_trace=e_res.get('exception', {}).get('stack_trace', '')
                        )
                        
                        # Roslyn data equivalent for runtime: list of classes/methods used in the path
                        roslyn_data_for_feedback = {"details_by_id": {}} # Simple stub for now
                        
                        # Analyze failure with intent awareness
                        runtime_feedback_analysis = self.analyzer.analyze_test_failure(test_failure, expected_intent=intent)
                        
                        mismatch = runtime_feedback_analysis.get('semantic_mismatch')
                        if mismatch:
                            actual_code = mismatch.get('actual_code')
                            print(f"[AutonomousSynthesizer] SEMANTIC MISMATCH detected: {actual_code} is NOT suitable for {intent}")
                            
                            # Update MethodStore with negative feedback
                            # Note: actual_code is class.method, MethodStore expects ID
                            # For now, we try to match the ID.
                            method_id = actual_code.lower()
                            self.synthesizer.method_store.record_semantic_feedback(method_id, intent, is_success=False)
                            print(f"[AutonomousSynthesizer] Penalty applied to {method_id} for intent {intent}")
                        # ----------------------------------------

                        runtime_feedback = self.analyzer.analyze_runtime_failure(e_res.get("exception", {}))
                        rec = None
                        for rb in runtime_feedback:
                            rec = rb.get("recommendation")
                        
                        # Heuristic regex/keyword-based corrections are disallowed.
                        
                        if rec == "AddFileCheck":
                            new_step = "もしファイルの存在が確認できれば"
                            if new_step not in design_steps:
                                print(f"[AutonomousSynthesizer] Injecting conditional safety step: {new_step}")
                                design_steps.insert(0, "ファイルの存在を確認する")
                                design_steps.insert(1, new_step)
                else:
                    return {
                        "status": "success",
                        "code": code,
                        "attempts": attempt,
                        "has_side_effects": result.get("has_side_effects"),
                        "poco_info": result.get("poco_info")
                    }
            
            # 4. 失敗分析と学習 (ビルドエラー)
            errors = v_res.get("errors", [])
            if not v_res.get("valid") and errors:
                print(f"[AutonomousSynthesizer] Build FAILED with {len(errors)} errors.")
                
                # --- NEW: Autonomous NuGet Resolution ---
                resolution_results = self.dependency_resolver.analyze_build_errors(errors)
                resolved_any = False
                
                for res in resolution_results:
                    if res.get("internal"):
                        # 内部コードの場合は using 句の欠落としてマーク
                        print(f"[AutonomousSynthesizer] Symbol '{res.get('id')}' found internally. Injecting reference hint.")
                        # 次の合成で using が追加されるようにヒントを与える（仮）
                        # TODO: self.synthesizer に直接 using 強制リストを渡す
                        resolved_any = True 
                    else:
                        pkg_id = res["name"]
                        if pkg_id not in session_dependencies:
                            print(f"[AutonomousSynthesizer] Found NuGet package: {pkg_id}")
                            session_dependencies.add(pkg_id)
                            resolved_any = True
                
                if resolved_any:
                    print("[AutonomousSynthesizer] Resolved missing symbols. Retrying synthesis.")
                    continue
                # -----------------------------------------

                for err in errors:
                    print(f"  - {err.get('code')}: {err.get('message')} (Line: {err.get('line')})")
                feedback = self.analyzer.analyze_compilation_failure(code, errors)
                
                if not feedback:
                    print("[AutonomousSynthesizer] No actionable feedback extracted. Stopping.")
                    break
                    
                for fb in feedback:
                    if fb["type"] == "negative_feedback":
                        src, tgt = fb["source_type"], fb["target_type"]
                        print(f"[AutonomousSynthesizer] Learning from mistake: {src} -> {tgt} is invalid.")
                        self.synthesizer.knowledge_base.add_negative_feedback(src, tgt)
                        
                        # 推薦アクションがあれば、設計ステップを動的に補完する
                        rec = fb.get("recommendation")
                        err_line = fb.get("line")
                        if rec == "ToString" and err_line:
                            insert_idx = max(0, len(design_steps) - 1)
                            new_step = "取得した値をToStringメソッドで文字列に変換する"
                            if new_step not in design_steps:
                                print(f"[AutonomousSynthesizer] Injecting fix step: {new_step}")
                                design_steps.insert(insert_idx, new_step)
                    
                    elif fb["type"] == "unresolved_symbol":
                        symbol = fb["symbol"]
                        # NuGet解決ループで解決できなかったものだけを永続化
                        if symbol not in session_dependencies:
                            print(f"[AutonomousSynthesizer] Marking symbol as dead-end: {symbol}")
                            # self.synthesizer.knowledge_base.add_unresolved_symbol(symbol)
            
            # 5. 知識ベースの更新をSynthesizerに反映
            # self.synthesizer.reload_feedback()
            
        return {
            "status": "partial_success",
            "message": "ビルド成功には至りませんでしたが、最適と思われるコードを返します。",
            "code": result.get("code", ""),
            "errors": v_res.get("errors", []),
            "attempts": attempt,
            "poco_info": result.get("poco_info", {})
        }

    def decompose_and_synthesize(self, goal: TDDGoal) -> Dict[str, Any]:
        """高レベルな目標を分解し、意図解析を交えて順次合成を実行する"""
        start_time = time.time()
        if not goal.description:
            return {"status": "error", "message": "目標の説明が空です。"}
        
        # 検蔵用サンドボックスの準備 (セッション内で共有)
        work_dir = tempfile.mkdtemp(prefix="tdd_shared_")
        try:
            # サンドボックスの初期化
            self.verifier.initialize_sandbox(work_dir)
            
            # POCO情報は IRGenerator が自動的に抽出するため、事前抽出ロジックを削除
            # main_type = list(inferred_poco.keys())[0] if inferred_poco else "Item"
            # main_collection = f"IEnumerable<{main_type}>"
            main_collection = "IEnumerable<dynamic>" # フォールバック
        
            requirements = []
            for i, criteria in enumerate(goal.acceptance_criteria):
                print(f"[AutonomousSynthesizer] Analyzing Requirement {i+1}: {criteria}")
                
                # コンテキスト作成と分析
                context = {"original_text": criteria, "analysis": {}}
                # Morph分析
                if hasattr(self.synthesizer, "morph_analyzer"):
                    context = self.synthesizer.morph_analyzer.analyze(context)
                
                # 構文解析 (chunks生成のために必要)
                self.syntactic_analyzer.analyze(context)
                
                # Intent detection via external heuristics is disabled for strict semantics.
                self.semantic_analyzer.analyze(context)
                
                intent = "GENERAL"
                entities = context.get("analysis", {}).get("entities", {})
                print(f"[DEBUG] Detected Intent: {intent}, Entities: {list(entities.keys())}")
                
                # 特殊ケース: メソッド名指定の意図がある場合
                if intent == "SET_METHOD_NAME" and "target_name" in entities:
                    target_name = entities["target_name"]["value"]
                    if requirements:
                        # 直前の要件のメソッド名を更新
                        print(f"[AutonomousSynthesizer] Renaming previous requirement to '{target_name}'")
                        requirements[-1]["method_name"] = target_name
                        continue 

                method_name = self._infer_method_name_from_analysis(intent, entities, criteria)
                requirements.append({
                    "id": f"req_{i}",
                    "description": criteria,
                    "intent": intent,
                    "entities": entities,
                    "method_name": method_name
                })
                
            final_results = []
            session_context = {
                "last_method": None,
                "methods_history": [],
                "inferred_poco": {}
            }
            
            for i, req in enumerate(requirements):
                m_name = req["method_name"]
                desc = req["description"]
                intent = req["intent"]
                entities = req["entities"]

                # --- 既存コードの再利用チェック (Semantic De-duplication) ---
                duplicates = self.structural_memory.find_duplicates(desc, threshold=0.1)
                if duplicates:
                    dup = duplicates[0]
                    self.logger.info(f"Detected potential duplicate in project: {dup['name']} (Sim: {dup['similarity']:.2f})")
                    self._inject_duplicate_to_store(dup)
                
                # 意図に基づくステップの強化
                steps = [desc]
                
                # 戻り値／引数の推論 (次のステップがある場合、READなら型を要求する)
                req_ret = None
                req_input = None
                
                if session_context["last_method"]:
                    prev_ret = session_context["last_method"].get("return_type")
                    if prev_ret and prev_ret.lower() != "void" and prev_ret != "Task":
                        req_input = prev_ret
                
                # 合成実行
                print(f"[AutonomousSynthesizer] Step {i+1}/{len(requirements)}: Synthesizing task: {m_name}")
                
                # CodeSynthesizer.synthesize は完成したコードを返すため、引数を調整
                res = self.synthesize_safely(m_name, steps, execute=True, session_context=session_context, return_type=req_ret, input_param_type=req_input, work_dir=work_dir, intent=intent)
                
                if res.get("code"):
                    sig = self._extract_signature(res["code"], m_name)
                    session_context["last_method"] = {
                        "name": m_name,
                        "code": res["code"],
                        "return_type": sig.get("return_type"),
                        "params": sig.get("params")
                    }
                    session_context["methods_history"].append(session_context["last_method"])
                
                final_results.append({
                    "requirement": req,
                    "result": res
                })
                
            # 結果の統合
            consolidated_code = self._consolidate_results(final_results)
            
            total_time = time.time() - start_time
            print(f"\n[AutonomousSynthesizer] Total Goal processing took {total_time:.2f}s")

            return {
                "status": "success",
                "results": final_results,
                "consolidated_code": consolidated_code
            }
        finally:
            if work_dir and os.path.exists(work_dir):
                shutil.rmtree(work_dir)

    @staticmethod
    def _build_call_template(cls_name: str, m_name: str, params: List[Dict[str, Any]]) -> str:
        """Call Pattern: 呼び出しテンプレートを生成する (ClassName.MethodName({p1}, {p2}))"""
        param_placeholders = [f"{{{p.get('name', f'p{i}')}}}" for i, p in enumerate(params)]
        return f"{cls_name}.{m_name}({', '.join(param_placeholders)})"

    def _inject_duplicate_to_store(self, dup_item: Dict[str, Any]):
        """プロジェクト内の重複メソッドを MethodStore に注入する。
        Call Pattern: メソッド本体の埋め込みではなく、型安全な呼び出しテンプレート
        (ClassName.MethodName({param1}, {param2})) を生成する。"""
        try:
            file_rel = dup_item.get("file", "")
            if not file_rel.lower().endswith(".cs"):
                # C#  synthesis では Python メソッドを再利用できない
                return

            body_code = self.structural_memory.get_method_code(dup_item)
            if not body_code:
                return

            m_name = dup_item.get("short_name") or dup_item["name"].split('.')[-1]
            cls_name = dup_item.get("class", "Global")
            sig = self._extract_signature(body_code, m_name)
            params = sig.get("params", [])

            # Call Pattern: 呼び出しテンプレートを生成 (コード埋め込みではなくメソッド呼び出し)
            call_template = self._build_call_template(cls_name, m_name, params)

            method_data = {
                "id": f"project.{dup_item['name']}",
                "name": m_name,
                "class": cls_name,
                "params": params,
                "return_type": sig.get("return_type", "void"),
                "code": call_template,
                "definition": body_code,
                "tags": ["project_internal", "reuse"],
                "summary": dup_item.get("summary", "")
            }

            self.logger.info(f"Injecting call pattern into store: {method_data['id']} -> {call_template}")
            self.synthesizer.method_store.add_method(method_data, overwrite=True)

        except Exception as e:
            self.logger.error(f"Failed to inject duplicate to store: {e}")

    def _consolidate_results(self, results: List[Dict[str, Any]]) -> str:
        """複数の合成結果を1つのクリーンなC#ファイルに統合する"""
        all_usings = set()
        method_bodies = []
        poco_definitions = {}
        
        for res in results:
            code = res["result"].get("code", "")
            if not code: continue
            
            # 1. Using の抽出
            usings = re.findall(r"using\s+[\w\.]+;", code)
            for u in usings: all_usings.add(u)
            
            # 2. メソッド定義の抽出
            # クラスの中身（メソッド部分）を正規表現で抜く
            # より堅牢な方法: GeneratedProcessor { ... } の中身をバランスの取れた括弧で探すか、
            # 単純に public ... ( 形式のメソッドを探す
            methods = re.findall(r"(public\s+(?:async\s+)?(?:Task<.*?>|Task|[a-zA-Z0-9_<>,\[\]]+)\s+\w+\s*\(.*?\)\s*\{(?:[^{}]*|\{[^{}]*\})*\})", code, re.DOTALL)
            for m in methods:
                method_bodies.append(m.strip())
            
            # 3. POCO 定義の抽出 (クラス定義の外にある public class ...)
            # res["result"] に poco_info がある場合はそれを利用
            poco_info = res["result"].get("poco_info", {})
            for name, props in poco_info.items():
                if name not in poco_definitions:
                    poco_definitions[name] = props.copy()
                else:
                    # 既存の定義があればマージ
                    existing_props = poco_definitions[name]
                    for p_name, p_type in props.items():
                        if p_name not in existing_props:
                            existing_props[p_name] = p_type

        # 4. 組み立て
        sorted_usings = sorted(list(all_usings))
        usings_str = "\n".join(sorted_usings)
        
        # メソッドのインデント調整 (クラス内に配置するため4スペース追加)
        indented_methods = []
        for body in method_bodies:
            # 正規化: 一旦最小限のインデントまで戻してから再インデント
            clean_body = textwrap.dedent(body).strip()
            indented_body = "\n".join([f"    {line}" if line.strip() else "" for line in clean_body.splitlines()])
            indented_methods.append(indented_body)
            
        combined_methods = "\n\n".join(indented_methods)
        
        poco_str = ""
        if poco_definitions:
            for name, props in poco_definitions.items():
                props_code = "\n".join([f"    public {t} {n} {{ get; set; }}" for n, t in props.items()])
                poco_str += f"\npublic class {name}\n{{\n{props_code}\n}}\n"
        else:
            # フォールバック: コードから直接クラス定義を探す (簡易的)
            for res in results:
                code = res["result"].get("code", "")
                poco_classes = re.findall(r"(public\s+class\s+([a-zA-Z0-9_]+)\s*\{(?:[^{}]*|\{[^{}]*\})*\})", code, re.DOTALL)
                for pc_code, pc_name in poco_classes:
                    if pc_name != "GeneratedProcessor" and pc_name not in poco_str:
                        # POCOも正規化
                        clean_pc = textwrap.dedent(pc_code).strip()
                        poco_str += f"\n{clean_pc}\n"
            
        # 最終的なクラス定義
        final_code = f"{usings_str}\n\npublic class GeneratedProcessor\n{{\n{combined_methods}\n}}\n{poco_str}"
        return final_code

    def _infer_method_name_from_analysis(self, intent: str, entities: Dict[str, Any], text: str) -> str:
        """IntentとEntityから適切なメソッド名を推測する"""
        
        # 1. Entity (target_name) があれば優先
        if "target_name" in entities:
             val = entities["target_name"]["value"]
             return "".join(word.capitalize() for word in re.split(r'[^a-zA-Z0-9]', val))
        
        # 2. Intent によるマッピング
        intent_map = {
            "FILE_CREATE": "Create",
            "FILE_READ": "Read",
            "FILE_WRITE": "Write",
            "FILE_APPEND": "Append",
            "CMD_RUN": "Execute",
            "EXTRACT_ENTITY": "Extract",
            "CS_QUERY_ANALYSIS": "Analyze"
        }
        
        if intent in intent_map:
            name = intent_map[intent]
            # Entity (filename) があれば結合
            if "filename" in entities:
                f_name = os.path.splitext(os.path.basename(entities["filename"]["value"]))[0]
                # CamelCase化
                f_name = "".join(word.capitalize() for word in re.split(r'[^a-zA-Z0-9]', f_name))
                return f"{name}{f_name}"
            return name
        
        # 3. 既定のルールベースへフォールバック
        return self._infer_method_name_from_criteria(text)

    def _infer_method_name_from_criteria(self, text: str) -> str:
        """要件文からメソッド名を推測する (簡易版)"""
        if "追加" in text or "Add" in text: return "Add"
        if "削除" in text or "Remove" in text: return "Remove"
        if "引く" in text or "Subtract" in text: return "Subtract"
        if "計算" in text or "Calculate" in text: return "Calculate"
        if "検索" in text or "Search" in text: return "Search"
        return "Features"
        
    def _extract_signature(self, code: str, method_name: str) -> Dict[str, Any]:
        """生成された C# コードからシグネチャを抽出する (簡易版)"""
        # public [Async] [ReturnType] [MethodName]([Params])
        pattern = fr"public\s+(?:async\s+)?([^\s]+)\s+{re.escape(method_name)}\s*\((.*?)\)"
        match = re.search(pattern, code)
        if match:
            ret_type = match.group(1)
            params_str = match.group(2)
            params = []
            if params_str.strip():
                for p in params_str.split(','):
                    parts = p.strip().split()
                    if len(parts) >= 2:
                        params.append({"type": parts[0], "name": parts[1]})
            return {"return_type": ret_type, "params": params}
        return {"return_type": "void", "params": []}
