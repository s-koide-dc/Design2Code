# -*- coding: utf-8 -*-
"""
AI Code Synthesis Demonstration Script (Strict StructuredSpec Dataflow)
Uses StructuredSpec steps and strict verification gates.
"""
import os
import re
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.config.config_manager import ConfigManager
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.code_verification.semantic_assertions import evaluate_blueprint_contract
from src.vector_engine.vector_engine import VectorEngine
from src.design_parser.validator import StructuredSpecValidationError


_DATA_SOURCE_INLINE_PATTERN = re.compile(r"^\[data_source\|([^\]]+)\]\s*(.*)$", re.IGNORECASE)
_ALLOWED_SOURCE_KINDS = {"db", "http", "file", "memory"}


def _step(
    text,
    kind="ACTION",
    intent="GENERAL",
    target="Item",
    output_type="void",
    side_effect="NONE",
    semantic_roles=None,
    role=None,
    cardinality=None,
    input_refs=None,
    logic=None,
    source_ref=None,
):
    return {
        "text": text,
        "kind": kind,
        "intent": intent,
        "target_entity": target,
        "output_type": output_type,
        "side_effect": side_effect,
        "semantic_roles": semantic_roles or {},
        "role": role,
        "cardinality": cardinality,
        "input_refs": input_refs,
        "logic": logic or [],
        "source_ref": source_ref,
    }


def _extract_inline_data_source(text):
    match = _DATA_SOURCE_INLINE_PATTERN.match(str(text or "").strip())
    if not match:
        return None, str(text or "")

    directive = match.group(1).strip()
    remainder = match.group(2).strip()
    parts = [p.strip() for p in directive.split("|") if p.strip()]
    if len(parts) == 1:
        token = parts[0].lower()
        if token in _ALLOWED_SOURCE_KINDS:
            return {"kind": token}, remainder
        return {"source_ref": parts[0]}, remainder
    if len(parts) == 2:
        return {"source_ref": parts[0], "kind": parts[1].lower()}, remainder
    return None, str(text or "")


def _build_structured_spec(name, purpose, raw_steps, data_sources=None):
    data_sources_resolved = list(data_sources or [])
    source_kind_by_id = {
        ds.get("id"): ds.get("kind")
        for ds in data_sources_resolved
        if isinstance(ds, dict) and isinstance(ds.get("id"), str) and isinstance(ds.get("kind"), str)
    }
    next_source_index_by_kind = {"db": 1, "http": 1, "file": 1, "memory": 1}

    def ensure_source(kind, preferred_id=None):
        resolved_kind = str(kind).lower()
        if resolved_kind not in _ALLOWED_SOURCE_KINDS:
            return None

        if preferred_id and preferred_id in source_kind_by_id:
            return preferred_id

        if preferred_id and preferred_id not in source_kind_by_id:
            ds = {"id": preferred_id, "kind": resolved_kind}
            data_sources_resolved.append(ds)
            source_kind_by_id[preferred_id] = resolved_kind
            return preferred_id

        for ds in data_sources_resolved:
            if isinstance(ds, dict) and ds.get("kind") == resolved_kind and isinstance(ds.get("id"), str):
                return ds["id"]

        candidate = f"source_{resolved_kind}_{next_source_index_by_kind.get(resolved_kind, 1)}"
        while candidate in source_kind_by_id:
            next_source_index_by_kind[resolved_kind] = next_source_index_by_kind.get(resolved_kind, 1) + 1
            candidate = f"source_{resolved_kind}_{next_source_index_by_kind[resolved_kind]}"
        next_source_index_by_kind[resolved_kind] = next_source_index_by_kind.get(resolved_kind, 1) + 1
        data_sources_resolved.append({"id": candidate, "kind": resolved_kind})
        source_kind_by_id[candidate] = resolved_kind
        return candidate

    steps = []
    for i, raw in enumerate(raw_steps, start=1):
        refs = raw.get("input_refs")
        if refs is None:
            refs = [f"step_{i-1}"] if i > 1 else []

        text = raw.get("text", "")
        ds_directive, normalized_text = _extract_inline_data_source(text)

        source_ref = raw.get("source_ref")
        if not source_ref and isinstance(ds_directive, dict):
            directive_ref = ds_directive.get("source_ref")
            directive_kind = ds_directive.get("kind")
            if directive_ref and directive_kind and directive_kind in _ALLOWED_SOURCE_KINDS:
                source_ref = ensure_source(directive_kind, preferred_id=directive_ref)
            elif directive_ref:
                source_ref = directive_ref
            elif directive_kind in _ALLOWED_SOURCE_KINDS:
                source_ref = ensure_source(directive_kind)

        if raw.get("intent") == "FETCH" and not source_ref:
            source_ref = ensure_source("file", preferred_id="source_default_file")

        step = {
            "id": f"step_{i}",
            "kind": raw.get("kind", "ACTION"),
            "intent": raw.get("intent", "GENERAL"),
            "target_entity": raw.get("target_entity", "Item"),
            "input_refs": refs,
            "output_type": raw.get("output_type", "void"),
            "side_effect": raw.get("side_effect", "NONE"),
            "text": normalized_text,
            "semantic_roles": raw.get("semantic_roles", {}),
            "depends_on": list(refs),
        }
        if raw.get("role"):
            step["role"] = raw["role"]
        if raw.get("cardinality"):
            step["cardinality"] = raw["cardinality"]
        if raw.get("logic"):
            step["logic"] = raw["logic"]
        if source_ref:
            step["source_ref"] = source_ref
            if source_ref in source_kind_by_id:
                step["source_kind"] = source_kind_by_id[source_ref]
        steps.append(step)

    return {
        "module_name": name,
        "purpose": purpose,
        "inputs": [{"name": "db", "type_format": "IDbConnection"}, {"name": "http", "type_format": "HttpClient"}],
        "outputs": [],
        "steps": steps,
        "constraints": [],
        "test_cases": [],
        "data_sources": data_sources_resolved,
    }


def run_demo():
    print("=== AI Code Synthesis Demo (Strict StructuredSpec) ===\n")

    print("[Init] Loading configuration and Method Store...")
    config = ConfigManager()

    from src.code_synthesis.method_store import MethodStore

    vector_engine = VectorEngine()
    method_store = MethodStore(config, vector_engine=vector_engine)
    synthesizer = CodeSynthesizer(config, method_store=method_store)

    scenarios = [
        {
            "name": "ProcessActiveUsers",
            "desc": "LINQ + File IO: ユーザーを取得し、条件で絞り込んでファイルに保存します。",
            "steps": [
                _step("全ユーザーを取得する", intent="FETCH", role="FETCH", target="User", cardinality="COLLECTION", output_type="IEnumerable<User>", semantic_roles={"path": "users.json"}),
                _step("価格が100より大きいアイテムで絞り込む", intent="LINQ", role="TRANSFORM", target="User", cardinality="COLLECTION", output_type="IEnumerable<User>", logic=[{"type": "comparison", "variable_hint": "Price", "operator": "Greater", "value": 100}]),
                _step("結果を active_users.txt に保存する", intent="FILE_IO", role="PERSIST", target="User", semantic_roles={"path": "active_users.txt"}),
            ],
        },
        {
            "name": "FetchProductInventory",
            "desc": "SQL + Console: データベースから在庫情報を取得して表示します。",
            "steps": [
                _step("SELECT * FROM Inventory を実行して商品を取得する", intent="DATABASE_QUERY", role="FETCH", target="Item", cardinality="COLLECTION", output_type="IEnumerable<Item>", semantic_roles={"sql": "SELECT * FROM Inventory"}, source_ref="source_inventory_db"),
                _step("取得した結果をコンソールに表示する", intent="DISPLAY", role="DISPLAY", target="Item"),
            ],
            "data_sources": [{"id": "source_inventory_db", "kind": "db", "description": "Inventory DB"}],
            "contract": {
                "disallow_placeholder_fetch": True,
                "require_display_property": "Name",
            },
        },
        {
            "name": "SyncExternalData",
            "desc": "HTTP + JSON: Web APIから情報を取得し、C#オブジェクトに変換します。",
            "steps": [
                _step("URL からJSONを非同期で取得する", intent="HTTP_REQUEST", role="FETCH", target="Product", output_type="string", semantic_roles={"url": "https://api.example.com/products"}),
                _step("取得した文字列をProductクラスのリストとしてデシリアライズする", intent="JSON_DESERIALIZE", role="TRANSFORM", target="Product", cardinality="COLLECTION", output_type="List<Product>"),
            ],
        },
        {
            "name": "RobustConfigLoader",
            "desc": "Logic + Resilience: 条件分岐とリトライを組み合わせた安全な読み込み。",
            "steps": [
                _step("config.json が存在するかチェックする", intent="EXISTS", role="EXISTS", output_type="bool", semantic_roles={"path": "config.json"}),
                _step("もし存在するならば", kind="CONDITION", intent="CONDITION", role="CONDITION", input_refs=["step_1"]),
                _step("ファイルを読み込む", intent="FILE_IO", role="READ", output_type="string", semantic_roles={"path": "config.json"}, input_refs=["step_1"]),
                _step("読み込んだ内容をコンソールに表示する", intent="DISPLAY", role="DISPLAY", input_refs=["step_3"]),
                _step("そうでなければ", kind="ELSE", intent="CONDITION", role="CONDITION", input_refs=["step_2"]),
                _step("エラーメッセージをコンソールに出力する", intent="DISPLAY", role="DISPLAY", semantic_roles={"content": "config.json not found"}, input_refs=["step_2"]),
                _step("を終えて", kind="END", intent="CONDITION", role="CONDITION", input_refs=["step_2"]),
            ],
            "contract": {
                "require_call_methods": ["File.Exists", "File.ReadAllText", "Console.WriteLine"],
                "require_var_usage_from_methods": [{"method_suffix": "File.ReadAllText"}],
            },
        },
        {
            "name": "BatchProcessProducts",
            "desc": "Loop + Console: 商品一覧を取得し、各アイテムの名前をコンソールに表示します。",
            "steps": [
                _step("全ての商品を取得する", intent="FETCH", role="FETCH", target="Item", cardinality="COLLECTION", output_type="IEnumerable<Item>", semantic_roles={"path": "products.json"}),
                _step("取得した各アイテムに対して", kind="LOOP", intent="LOOP", role="LOOP", target="Item", input_refs=["step_1"]),
                _step("アイテムの名前をコンソールに表示する", intent="DISPLAY", role="DISPLAY", target="Item", input_refs=["step_2"]),
                _step("を終えて", kind="END", intent="LOOP", role="LOOP", input_refs=["step_2"]),
            ],
            "contract": {
                "disallow_placeholder_fetch": True,
                "require_display_property": "Name",
            },
        },
        {
            "name": "ComplexLinqSearch",
            "desc": "LINQ: 'A'で始まる名前、かつ価格が500より大きいユーザーを抽出します。",
            "steps": [
                _step("全ユーザーを取得する", intent="FETCH", role="FETCH", target="User", cardinality="COLLECTION", output_type="IEnumerable<User>", semantic_roles={"path": "users.json"}),
                _step("名前が A で始まり、かつ価格が500より大きいユーザーを抽出する", intent="LINQ", role="TRANSFORM", target="User", cardinality="COLLECTION", output_type="IEnumerable<User>", logic=[{"type": "comparison", "variable_hint": "Name", "operator": "StartsWith", "value": "A"}, {"type": "comparison", "variable_hint": "Price", "operator": "Greater", "value": 500}]),
                _step("結果をコンソールに表示する", intent="DISPLAY", role="DISPLAY", target="User"),
            ],
            "contract": {
                "disallow_placeholder_fetch": True,
                "require_display_property": "Name",
            },
        },
        {
            "name": "CalculateOrderDiscount",
            "desc": "Complex Logic: 注文を取得し、条件に応じて割引率を計算し保存、ログを出力します。",
            "steps": [
                _step("全ての注文を取得する", intent="FETCH", role="FETCH", target="Order", cardinality="COLLECTION", output_type="IEnumerable<Order>", semantic_roles={"path": "orders.json"}),
                _step("取得した各アイテムに対して", kind="LOOP", intent="LOOP", role="LOOP", target="Order", input_refs=["step_1"]),
                _step("もし合計が5000より大きく、かつ顧客タイプが Premium ならば", kind="CONDITION", intent="CONDITION", role="CONDITION", target="Order", input_refs=["step_2"]),
                _step("金額を合計の15%として計算する", intent="CALC", role="CALC", target="Order", output_type="decimal", input_refs=["step_3"]),
                _step("そうでなければ", kind="ELSE", intent="CONDITION", role="CONDITION", input_refs=["step_3"]),
                _step("金額を合計の5%として計算する", intent="CALC", role="CALC", target="Order", output_type="decimal", input_refs=["step_3"]),
                _step("を終えて", kind="END", intent="CONDITION", role="CONDITION", input_refs=["step_3"]),
                _step("割引を保存する", intent="PERSIST", role="PERSIST", target="Order", input_refs=["step_2"]),
                _step("を終えて", kind="END", intent="LOOP", role="LOOP", input_refs=["step_2"]),
                _step("コンソールに完了メッセージを表示する", intent="DISPLAY", role="DISPLAY", semantic_roles={"content": "Discount processing complete"}, input_refs=["step_1"]),
            ],
        },
    ]

    from src.code_verification.compilation_verifier import CompilationVerifier
    from src.utils.nuget_client import NuGetClient

    verifier = CompilationVerifier(config)
    nc = NuGetClient(config)

    for i, s in enumerate(scenarios, 1):
        print(f"\nScenario {i}: {s['name']}")
        print(f"Description: {s['desc']}")

        structured_spec = _build_structured_spec(s["name"], s["desc"], s["steps"], data_sources=s.get("data_sources"))
        try:
            result = synthesizer.synthesize_from_structured_spec(
                method_name=s["name"],
                structured_spec=structured_spec,
                return_trace=True,
            )
        except StructuredSpecValidationError as e:
            print(">> Status: FAILED (StructuredSpec validation)")
            print(f"   - {e}")
            continue

        if s["name"] == "CalculateOrderDiscount":
            print(f"--- [DEBUG] IR Tree for {s['name']} ---")
            for node in result.get("trace", {}).get("ir_tree", {}).get("logic_tree", []):
                print(f"  Node: {node.get('type')}, Intent: {node.get('intent')}, Logic: {node.get('semantic_map', {}).get('logic')}")
                if node.get("children"):
                    for child in node["children"]:
                        print(f"    Child Node: {child.get('type')}, Intent: {child.get('intent')}, Logic: {child.get('semantic_map', {}).get('logic')}")
        
        current_code = result["code"]
        current_deps = result.get("dependencies", [])

        has_todos = "// TODO" in current_code

        deps = []
        for d in current_deps:
            if d in ["System", "System.Linq", "System.IO", "System.Collections.Generic", "GeneratedProcessor"]:
                continue
            pkg = nc.resolve_package(d)
            if pkg:
                deps.append(pkg)
            else:
                deps.append({"name": d, "version": "*"})

        if any(kw in current_code for kw in ["Dapper", ".Query", ".Execute"]):
            if not any(d["name"] == "Dapper" for d in deps):
                deps.append({"name": "Dapper", "version": "2.1.35"})
        if "Sqlite" in current_code:
            if not any(d["name"] == "Microsoft.Data.Sqlite" for d in deps):
                deps.append({"name": "Microsoft.Data.Sqlite", "version": "9.0.0"})

        v_result = verifier.verify(current_code, dependencies=deps)
        is_valid = v_result.get("valid", False)

        semantic_issues = []
        trace = result.get("trace", {}) if isinstance(result, dict) else {}
        blueprint = trace.get("blueprint") if isinstance(trace, dict) else None
        contract = s.get("contract")
        if isinstance(contract, dict) and isinstance(blueprint, dict):
            semantic_issues = evaluate_blueprint_contract(blueprint, contract)

        print("\n--- Final Generated C# Code ---")
        print(current_code)
        print("-------------------------\n")

        if has_todos:
            print(">> Status: FAILED (Strict mode: TODO remains)")
            continue
        if not is_valid:
            errors = v_result.get("errors", [])
            print(f">> Status: FAILED (Compilation errors: {len(errors) if isinstance(errors, list) else 1})")
            if isinstance(errors, list):
                for e in errors:
                    print(f"   - {e.get('code')}: {e.get('message')}")
            else:
                print(f"   - {errors}")
            continue
        if semantic_issues:
            print(f">> Status: FAILED (Semantic assertions: {len(semantic_issues)})")
            for issue in semantic_issues:
                print(f"   - {issue}")
            continue

        out_path = f"demo_gen_{s['name']}.cs"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(current_code)
        print(">> Status: FULLY SYNTHESIZED")
        print(f"Result saved to {out_path}")

    print("\n=== Demo Complete ===")


if __name__ == "__main__":
    run_demo()
