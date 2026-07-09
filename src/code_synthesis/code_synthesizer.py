# -*- coding: utf-8 -*-
import json
import os
import copy
from typing import List, Dict, Any

from src.code_synthesis.type_system import TypeSystem
from src.symbol_matching.symbol_matcher import SymbolMatcher
from src.morph_analyzer.morph_analyzer import MorphAnalyzer
from src.utils.code_builder_client import CodeBuilderClient

# New specialized components
from src.code_synthesis.statement_builder import StatementBuilder
from src.code_synthesis.blueprint_assembler import BlueprintAssembler
from src.code_synthesis.template_registry import TemplateRegistry
from src.code_synthesis.semantic_binder import SemanticBinder
from src.code_synthesis.action_synthesizer import ActionSynthesizer

from src.utils.logic_auditor import LogicAuditor
from src.utils.semantic_intents import (
    INTENT_FETCH,
    INTENT_GENERAL,
    INTENT_JSON_DESERIALIZE,
    INTENT_PERSIST,
    INTENT_RETURN,
    INTENT_TRANSFORM,
    NODE_ACTION,
)

class CodeSynthesizer:
    """[Phase 23.3: Pure Orchestration] Design-to-Code の中心的なオーケストレータークラス。"""

    def __init__(self, config, method_store=None, morph_analyzer=None, matcher=None):
        self.config = config
        self.morph_analyzer = morph_analyzer or MorphAnalyzer(config_manager=config)
        if method_store is None:
            from src.code_synthesis.method_store import MethodStore
            method_store = MethodStore(config=config)
        self.method_store = method_store
        root = getattr(config, 'workspace_root', os.getcwd())
        from src.code_synthesis.unified_knowledge_base import UnifiedKnowledgeBase
        from src.autonomous_learning.structural_memory import StructuralMemory
        storage_dir = getattr(config, 'storage_dir', os.path.join(root, "cache"))
        self.structural_memory = StructuralMemory(
            storage_dir,
            config_manager=config,
            vector_engine=getattr(method_store, "vector_engine", None),
            morph_analyzer=self.morph_analyzer,
        )
        self.ukb = UnifiedKnowledgeBase(config, method_store, self.structural_memory)
        from src.planner.htn_planner import HTNPlanner
        self.planner = HTNPlanner(self.ukb)
        schema_path = os.path.join(root, "resources", "entity_schema.json")
        self.entity_schema = {}
        if not os.path.exists(schema_path):
            fallback_root = os.getcwd()
            if fallback_root != root:
                fallback_path = os.path.join(fallback_root, "resources", "entity_schema.json")
                if os.path.exists(fallback_path):
                    schema_path = fallback_path
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                self.entity_schema = json.load(f)
        self.type_system = TypeSystem()
        self.matcher = matcher or SymbolMatcher(config_manager=config, morph_analyzer=self.morph_analyzer, vector_engine=getattr(method_store, 'vector_engine', None), knowledge_base=self.ukb)
        self.matcher.synthesizer = self
        self.logic_auditor = LogicAuditor(
            morph_analyzer=self.morph_analyzer,
            vector_engine=getattr(self.matcher, "vector_engine", None),
            knowledge_base=self.ukb
        )
        self.stmt_builder = StatementBuilder(self.type_system, entity_schema=self.entity_schema, structural_memory=self.structural_memory, knowledge_base=self.ukb)
        self.blueprint_assembler = BlueprintAssembler()
        self.template_registry = TemplateRegistry()
        self.semantic_binder = SemanticBinder(self.type_system, self.matcher, knowledge_base=self.ukb, stmt_builder=self.stmt_builder, config=self.config, morph_analyzer=self.morph_analyzer)
        self.action_synthesizer = ActionSynthesizer(self)
        from src.code_synthesis.ir_emitter import IREmitter
        self.ir_emitter = IREmitter(self)
        self.builder_client = CodeBuilderClient(config)
        self.design_steps_history = []
        strict_cfg = {}
        if hasattr(config, "get_section"):
            strict_cfg = config.get_section("generation") or {}
        if not isinstance(strict_cfg, dict):
            strict_cfg = {}
        self.strict_semantics = bool(strict_cfg.get("strict_semantics", False))

    def synthesize(self, method_name: str, design_steps: Any, return_type: str = None, input_type_hint: str = None, pre_resolved_dependencies: List[str] = None, intent: str = None, **kwargs) -> Dict[str, Any]:
        """
        Backward-compatible entry point.
        Accepts either a list of step strings or a structured_spec dict.
        """
        if isinstance(design_steps, list) and not os.path.exists(self.builder_client.project_path):
            name_to_id = {}
            for method_id, metadata in (self.method_store.metadata_by_id or {}).items():
                method_name_value = str(metadata.get("name") or "").strip()
                if method_name_value:
                    name_to_id.setdefault(method_name_value.lower(), str(method_id))
                name_to_id.setdefault(str(method_id).lower(), str(method_id))
            structured_steps = []
            for index, step_value in enumerate(design_steps, start=1):
                supplied_step = dict(step_value) if isinstance(step_value, dict) else {}
                step_text = str(
                    supplied_step.get("text")
                    or supplied_step.get("original_text")
                    or step_value
                ).strip()
                explicit_id = (
                    supplied_step.get("explicit_method_id")
                    or name_to_id.get(step_text.lower())
                )
                normalized_step = {
                    "id": f"step_{index}",
                    "kind": NODE_ACTION,
                    "intent": INTENT_GENERAL,
                    "target_entity": "Item",
                    "input_refs": [f"step_{index-1}"] if index > 1 else [],
                    "output_type": "void",
                    "side_effect": "NONE",
                    "text": step_text,
                    "explicit_method_id": explicit_id,
                    "explicit_method_name": (
                        self.method_store.metadata_by_id.get(explicit_id, {}).get("name")
                        if explicit_id
                        else None
                    ),
                }
                normalized_step.update(supplied_step)
                normalized_step["text"] = step_text
                structured_steps.append(normalized_step)
            structured_spec = {
                "module_name": method_name,
                "purpose": f"{method_name} synthesis",
                "inputs": [],
                "outputs": [],
                "constraints": [],
                "test_cases": [],
                "steps": structured_steps,
                "data_sources": [],
            }
            return self.synthesize_from_structured_spec(
                method_name,
                structured_spec,
                intent=intent,
                return_type=return_type,
                input_type_hint=input_type_hint,
                pre_resolved_dependencies=pre_resolved_dependencies,
                **kwargs,
            )
        if isinstance(design_steps, dict) and "steps" in design_steps:
            structured_spec = design_steps
        else:
            steps_list = design_steps if isinstance(design_steps, list) else [str(design_steps)]
            structured_steps = []
            name_to_id = {}
            if getattr(self.method_store, "metadata_by_id", None):
                for m_id, meta in self.method_store.metadata_by_id.items():
                    m_name = str(meta.get("name") or "").strip()
                    if m_name:
                        name_to_id.setdefault(m_name.lower(), str(m_id))
                    if m_id:
                        name_to_id.setdefault(str(m_id).lower(), str(m_id))
            data_sources = []
            for i, step_text in enumerate(steps_list, start=1):
                text = str(step_text).strip()
                explicit_id = name_to_id.get(text.lower())
                structured_steps.append({
                    "id": f"step_{i}",
                    "kind": NODE_ACTION,
                    "intent": INTENT_GENERAL,
                    "target_entity": "Item",
                    "input_refs": [f"step_{i-1}"] if i > 1 else [],
                    "output_type": "void",
                    "side_effect": "NONE",
                    "text": text,
                    "explicit_method_id": explicit_id,
                    "explicit_method_name": self.method_store.metadata_by_id.get(explicit_id, {}).get("name") if explicit_id else None
                })
            structured_spec = {
                "module_name": method_name,
                "purpose": f"{method_name} synthesis",
                "inputs": [],
                "outputs": [],
                "constraints": [],
                "test_cases": [],
                "steps": structured_steps,
                "data_sources": data_sources
            }
        return self.synthesize_from_structured_spec(
            method_name,
            structured_spec,
            intent=intent,
            return_type=return_type,
            input_type_hint=input_type_hint,
            pre_resolved_dependencies=pre_resolved_dependencies,
            **kwargs
        )

    def synthesize_from_structured_spec(self, method_name: str, structured_spec: Dict[str, Any], intent: str = None, return_type: str = None, input_type_hint: str = None, **kwargs) -> Dict[Any, Any]:
        from src.design_parser import validate_structured_spec_or_raise
        from src.ir_generator.ir_generator import IRGenerator
        validate_structured_spec_or_raise(structured_spec)

        # 27.138: Pre-resolve source info before IR generation
        source_map = {ds["id"]: ds["kind"] for ds in structured_spec.get("data_sources", [])}
        for step in structured_spec.get("steps", []):
            if isinstance(step, dict) and step.get("source_ref") in source_map:
                step["source_kind"] = source_map[step["source_ref"]]

        steps = structured_spec.get("steps", [])
        inputs = structured_spec.get("inputs", [])
        inferred_input_type = None
        self.design_steps_history = [s.get("text", "") for s in steps if isinstance(s, dict)]

        # 27.200: Infer return type if not specified
        if not return_type:
            outputs = structured_spec.get("outputs", [])
            if outputs and isinstance(outputs, list):
                out_type = outputs[0].get("type_format") if isinstance(outputs[0], dict) else None
                if isinstance(out_type, str) and out_type.strip():
                    return_type = out_type.strip()
        if not return_type and steps:
            last_step = steps[-1]
            if isinstance(last_step, dict) and last_step.get("intent") in [INTENT_FETCH, INTENT_JSON_DESERIALIZE, INTENT_TRANSFORM]:
                return_type = last_step.get("output_type")

        entity_schema = getattr(self.method_store, 'entity_schema', self.entity_schema)
        ir_gen = IRGenerator(self.config, knowledge_base=self.ukb, method_store=self.method_store, morph_analyzer=self.morph_analyzer, entity_schema=copy.deepcopy(entity_schema), matcher=self.matcher)
        ir_tree = ir_gen.from_structured_spec(structured_spec, intent_hint=intent)

        # 27.405: CRITICAL - Propagate return type hint to IR tree for path initialization
        if return_type:
            ir_tree["return_type_hint"] = return_type

        def _is_void_input(inp: Dict[str, Any]) -> bool:
            t = str(inp.get("type_format") or "").strip().lower()
            desc = str(inp.get("description") or "").strip().lower()
            return t in ["void", "none"] or (not t and desc in ["none", ""])

        input_defs = []
        if inputs and isinstance(inputs, list):
            for i, inp in enumerate(inputs, start=1):
                if not isinstance(inp, dict):
                    continue
                if _is_void_input(inp):
                    continue
                name = inp.get("name") or f"input_{i}"
                if not inp.get("type_format"):
                    inp["type_format"] = inferred_input_type or "object"
                input_defs.append({"name": name, "type": inp.get("type_format") or "object"})

        return self._synthesize_from_ir_tree(method_name=method_name, ir_tree=ir_tree, expected_steps=len(steps), return_type=return_type, input_type_hint=input_type_hint, input_defs=input_defs, **kwargs)

    def _synthesize_from_ir_tree(self, method_name: str, ir_tree: Dict[str, Any], expected_steps: int, return_type: str = None, input_type_hint: str = None, **kwargs) -> Dict[Any, Any]:
        type_vars = {}
        input_defs = kwargs.get("input_defs") or []
        for inp in input_defs:
            name = inp.get("name")
            t = inp.get("type") or "object"
            if name:
                type_vars.setdefault(t, []).append({"var_name": name, "role": "input", "node_id": "input"})
        if input_type_hint and "input_name" in kwargs:
            type_vars.setdefault(input_type_hint, []).append({"var_name": kwargs["input_name"], "role": "input", "node_id": "input"})

        used_names = set(["db", "http", "logger", "_logger", "_httpClient", "_dbConnection"])
        for inp in input_defs:
            if inp.get("name"):
                used_names.add(inp["name"])
        initial_path = {
            "consumed_ids": set(),
            "completed_nodes": 0,
            "statements": [],
            "type_to_vars": type_vars,
            "used_names": used_names,
            "all_usings": set(),
            "poco_defs": {},
            "method_return_type": ir_tree.get("return_type_hint") or "void",
            "last_literal_map": {}, # Phase 7 F-1
            "input_defs": input_defs,
            "dependencies": set()
        }
        # 27.502: Re-propagate to path for direct access by statement builder
        if ir_tree.get("return_type_hint"):
            initial_path["method_return_type"] = ir_tree["return_type_hint"]

        final_paths = self.ir_emitter.emit(ir_tree, [initial_path], beam_width=10)
        if not final_paths:
            return {
                "status": "error",
                "code": "",
                "dependencies": [],
                "error": {
                    "type": "synthesis_resolution_failed",
                    "reason": "no_valid_paths",
                },
                "trace": {"ir_tree": ir_tree},
            }

        best_path = sorted(
            final_paths,
            key=lambda p: (p.get("completed_nodes", 0), len(p.get("statements", []))),
            reverse=True
        )[0]
        self._audit_reachability(best_path)

        # Fallback: if some nodes were not synthesized, try a direct UKB-based pass.
        allow_fallback = kwargs.get("allow_fallback", True)
        if self.strict_semantics:
            allow_fallback = False
        if ((best_path.get("completed_nodes", 0) < expected_steps) or (len(best_path.get("statements", [])) < expected_steps)) and allow_fallback and self.ukb is not None and hasattr(self.ukb, "search"):
            for node in ir_tree.get("logic_tree", []):
                if node.get("id") in best_path.get("consumed_ids", set()):
                    continue
                try:
                    query_text = node.get("original_text", "")
                    requested_return_type = node.get("output_type")
                    if requested_return_type in (None, "", "void"):
                        requested_return_type = None
                    candidates = self.ukb.search(
                        query_text,
                        limit=5,
                        intent=node.get("intent"),
                        target_entity=node.get("target_entity"),
                        return_type=requested_return_type,
                        requested_role=self.action_synthesizer._get_effective_runtime_role(node),
                        source_kind=node.get("source_kind"),
                    )
                except Exception:
                    candidates = []
                for m in candidates:
                    res = self.action_synthesizer._synthesize_single_method(m, node, best_path, node.get("target_entity", "Item"))
                    if res:
                        best_path = res
                        break

        unresolved_errors = []
        seen_resolution_errors = set()
        for error in best_path.get("resolution_errors", []):
            identity = (
                error.get("node_id"),
                error.get("reason"),
            )
            if identity in seen_resolution_errors:
                continue
            seen_resolution_errors.add(identity)
            unresolved_errors.append(error)
        consumed_ids = best_path.get("consumed_ids", set())
        for node in ir_tree.get("logic_tree", []):
            node_id = node.get("id")
            if node_id in consumed_ids:
                continue
            identity = (node_id, "node_not_synthesized")
            if identity in seen_resolution_errors:
                continue
            seen_resolution_errors.add(identity)
            unresolved_errors.append({
                "node_id": node_id,
                "reason": "node_not_synthesized",
                "details": {
                    "intent": node.get("intent"),
                    "target_entity": node.get("target_entity"),
                    "output_type": node.get("output_type"),
                },
            })
        if unresolved_errors:
            return {
                "status": "error",
                "code": "",
                "dependencies": [],
                "error": {
                    "type": "synthesis_resolution_failed",
                    "reason": "unresolved_ir_nodes",
                    "unresolved_nodes": unresolved_errors,
                    "completed_nodes": best_path.get("completed_nodes", 0),
                    "expected_steps": expected_steps,
                },
                "trace": {
                    "ir_tree": ir_tree,
                    "best_path": best_path,
                },
            }

        # 27.410: Interface alignment with BlueprintAssembler
        blueprint = self.blueprint_assembler.create_blueprint(
            method_name,
            best_path,
            inputs=kwargs.get("input_defs") or [],
            ir_tree=ir_tree
        )
        def _should_emit_entity_class(entity_name: str, path: Dict[str, Any]) -> bool:
            has_reference = False
            for t in path.get("type_to_vars", {}).keys():
                if entity_name in str(t):
                    has_reference = True
                    break
            if not has_reference:
                for stmt in path.get("statements", []):
                    for key in ["code", "method", "call_expr", "var_type"]:
                        val = stmt.get(key)
                        if isinstance(val, str) and entity_name in val:
                            has_reference = True
                            break
                    if has_reference:
                        break
                    for body_key in ["body", "else_body"]:
                        if isinstance(stmt.get(body_key), list):
                            for inner in stmt[body_key]:
                                for key in ["code", "method", "call_expr", "var_type"]:
                                    val = inner.get(key)
                                    if isinstance(val, str) and entity_name in val:
                                        has_reference = True
                                        break
                                if has_reference:
                                    break
                    if has_reference:
                        break
            if not has_reference:
                return False
            return entity_name in (path.get("poco_defs") or {}) or has_reference

        # 27.505: Use CodeBuilderClient officially
        res = self.builder_client.build_code(blueprint)
        if res.get("status") == "error":
            return {
                "status": "error",
                "code": "",
                "dependencies": [],
                "error": {
                    "type": "code_generation_failed",
                    "reason": "invalid_or_unrenderable_blueprint",
                    "details": (
                        res.get("errors")
                        or res.get("diagnostics")
                        or res.get("message")
                    ),
                },
                "trace": {
                    "ir_tree": ir_tree,
                    "best_path": best_path,
                    "blueprint": blueprint,
                },
            }
        code = res.get("code") or ""

        pre_resolved = kwargs.get("pre_resolved_dependencies") or []
        dep_set = []
        path_deps = best_path.get("dependencies")
        if isinstance(path_deps, set):
            dep_set = list(path_deps)
        elif isinstance(path_deps, list):
            dep_set = list(path_deps)
        resolved = []
        for d in pre_resolved:
            if d and d not in resolved:
                resolved.append(d)
        for d in dep_set:
            if d and d not in resolved:
                resolved.append(d)

        return {
            "status": "success",
            "code": code,
            "dependencies": resolved,
            "trace": {
                "ir_tree": ir_tree,
                "best_path": best_path,
                "blueprint": blueprint
            }
        }

    def _copy_path(self, path: Dict[str, Any]) -> Dict[str, Any]:
        new_path = {
            "consumed_ids": path["consumed_ids"].copy(),
            "completed_nodes": path["completed_nodes"],
            "statements": list(path["statements"]),
            "type_to_vars": {k: list(v) for k, v in path["type_to_vars"].items()},
            "used_names": path["used_names"].copy(),
            "all_usings": path["all_usings"].copy(),
            "poco_defs": copy.deepcopy(path["poco_defs"]),
            "method_return_type": path.get("method_return_type", "void"),
            "is_async_needed": path.get("is_async_needed", False),
            "name_to_role": path.get("name_to_role", {}).copy(),
            "last_literal_map": path.get("last_literal_map", {}).copy(), # Phase 7 F-1
            "input_defs": path.get("input_defs", [])
        }
        if "resolution_errors" in path:
            new_path["resolution_errors"] = copy.deepcopy(
                path["resolution_errors"]
            )
        if "active_scope_item" in path: new_path["active_scope_item"] = path["active_scope_item"]
        if "hoisted_statements" in path: new_path["hoisted_statements"] = list(path["hoisted_statements"])
        if "in_loop" in path: new_path["in_loop"] = path["in_loop"]
        if "referenced_fields" in path: new_path["referenced_fields"] = path["referenced_fields"].copy()
        if "field_type_map" in path: new_path["field_type_map"] = path["field_type_map"].copy()
        if "dependencies" in path:
            deps = path["dependencies"]
            new_path["dependencies"] = deps.copy() if isinstance(deps, set) else list(deps)
        if "extra_code" in path:
            new_path["extra_code"] = list(path["extra_code"])
        return new_path

    def _audit_reachability(self, path: Dict[str, Any]):
        """[Phase 7 F-2] データの Source から Sink への到達性を検証する監査ロジック"""
        sink_intents = ["PERSIST", "DISPLAY", "RETURN", "NOTIFICATION"]
        name_to_role = path.get("name_to_role", {})

        # 1. 重要な結果変数（Source 由来）を特定
        sources = []
        for name, role in name_to_role.items():
            if role in ["content", "data", "accumulator"]:
                sources.append(name)

        # 2. ステートメントをスキャンして利用状況をチェック
        consumed_vars = set()

        from src.utils.text_parser import contains_word

        def _raw_uses_var(code_text: str, var_name: str) -> bool:
            if not code_text or not var_name:
                return False
            return contains_word(code_text, var_name)

        def check_consumption(statements):
            for stmt in statements:
                consumes = stmt.get("consumes", [])
                if consumes:
                    for s in sources:
                        if s in consumes:
                            consumed_vars.add(s)
                s_type = stmt.get("type")
                if s_type == "foreach":
                    source = stmt.get("source")
                    if isinstance(source, str) and source in sources:
                        consumed_vars.add(source)
                    if stmt.get("body"):
                        check_consumption(stmt.get("body", []))
                    continue
                if s_type == "call":
                    args = stmt.get("args", [])

                    # 引数として使われているか
                    for s in sources:
                        usage_found = False
                        for arg in args:
                            if isinstance(arg, str) and arg.strip() == s:
                                usage_found = True
                                break
                            if isinstance(arg, dict) and arg.get("var") == s:
                                usage_found = True
                                break

                        if usage_found:
                            # Sink インテントでの利用か確認
                            if stmt.get("intent") in sink_intents:
                                consumed_vars.add(s)
                            # または他の変数への代入を経由しているか（簡略化のため消費とみなす）
                            elif stmt.get("out_var"):
                                consumed_vars.add(s)
                if s_type == "raw":
                    code_text = str(stmt.get("code", "") or "")
                    if stmt.get("intent") in sink_intents:
                        for s in sources:
                            if _raw_uses_var(code_text, s):
                                consumed_vars.add(s)
                    if stmt.get("out_var"):
                        for s in sources:
                            if _raw_uses_var(code_text, s):
                                consumed_vars.add(s)
                    if code_text.strip().startswith("return"):
                        for s in sources:
                            if _raw_uses_var(code_text, s):
                                consumed_vars.add(s)

                if "body" in stmt: check_consumption(stmt["body"])
                if "else_body" in stmt: check_consumption(stmt["else_body"])

        check_consumption(path.get("statements", []))

        # 3. 到達していない変数を警告としてコメント挿入
        orphans = [s for s in sources if s not in consumed_vars]
        if orphans:
            warning = f"// WARNING: [F-2 Audit] Data in {', '.join(orphans)} may be lost (never reached a Sink)."
            path["statements"].append({"type": "comment", "text": warning})
