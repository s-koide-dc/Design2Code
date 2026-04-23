from __future__ import annotations

from typing import Any, Dict, List

from src.design_parser import validate_structured_spec_or_raise


def build_input_defs(spec: dict) -> list:
    input_defs = []
    inputs = spec.get("inputs", []) if isinstance(spec, dict) else []
    def _is_void_input(inp: Dict[str, Any]) -> bool:
        t = str(inp.get("type_format") or "").strip().lower()
        desc = str(inp.get("description") or "").strip().lower()
        return t in ["void", "none"] or (not t and desc in ["none", ""])
    if isinstance(inputs, list):
        for i, inp in enumerate(inputs, start=1):
            if not isinstance(inp, dict):
                continue
            if _is_void_input(inp):
                continue
            name = inp.get("name") or f"input_{i}"
            input_type = inp.get("type_format") or "object"
            input_defs.append({"name": name, "type": input_type})
    return input_defs


def resolve_nuget_deps(usings: list, nuget_client) -> list:
    if nuget_client is None:
        return []
    fallback = {
        "Dapper": {"name": "Dapper", "version": "2.1.35"},
        "Newtonsoft.Json": {"name": "Newtonsoft.Json", "version": "13.0.3"},
        "Microsoft.Extensions.Logging": {"name": "Microsoft.Extensions.Logging", "version": "8.0.0"},
    }
    return nuget_client.resolve_packages_from_usings(usings, fallback=fallback)


def synthesize_structured_spec(
    synthesizer,
    structured_spec: dict,
    method_name: str,
    *,
    return_trace: bool = True,
    verifier=None,
    replanner=None,
    spec_auditor=None,
    nuget_client=None,
    allow_retry: bool = False,
    allow_fallback: bool = True,
    max_retries: int = 3,
) -> Dict[str, Any]:
    validate_structured_spec_or_raise(structured_spec)

    result = synthesizer.synthesize_from_structured_spec(
        method_name=method_name,
        structured_spec=structured_spec,
        return_trace=return_trace,
        allow_fallback=allow_fallback,
    )
    if not isinstance(result, dict):
        return {"status": "FAILED", "code": "UNKNOWN_RESULT"}
    if result.get("status") == "FAILED":
        return result

    code = result.get("code", "")
    trace = result.get("trace", {}) if isinstance(result.get("trace"), dict) else {}
    ir_tree = trace.get("ir_tree")

    spec_issues = []
    if spec_auditor is not None:
        try:
            spec_issues = spec_auditor.audit(structured_spec, result)
        except Exception:
            spec_issues = []

    dependencies = result.get("dependencies", []) or []
    resolved_deps = resolve_nuget_deps(dependencies, nuget_client)
    v_result = {"valid": True, "errors": []}
    if verifier is not None:
        v_result = verifier.verify(code, dependencies=resolved_deps)

    if not allow_retry or replanner is None:
        result["spec_issues"] = spec_issues
        result["verification"] = v_result
        result["resolved_dependencies"] = resolved_deps
        return result

    retry_count = 0
    while retry_count < max_retries:
        has_todo = "// TODO" in code
        is_valid = v_result.get("valid", False)
        mismatch_hints = []
        if replanner is not None:
            mismatch_hints = replanner.analyzer.analyze_logic_mismatch(ir_tree, result)
        has_logic_error = len(mismatch_hints) > 0
        blocking_spec = any(str(issue).startswith("SPEC_INPUT_LINK_UNUSED") for issue in spec_issues)

        if is_valid and not has_todo and not has_logic_error and not spec_issues:
            break
        if not allow_retry:
            break

        retry_count += 1
        semantic_issues = []
        if has_todo:
            semantic_issues.append("GENERATED_CODE_CONTAINS_TODOS")
        if spec_issues:
            semantic_issues.extend(spec_issues)
        if blocking_spec and "SPEC_INPUT_LINK_UNUSED" not in semantic_issues:
            semantic_issues.append("SPEC_INPUT_LINK_UNUSED")

        if replanner is None:
            break
        replan_res = replanner.replan(structured_spec, ir_tree, result, v_result, semantic_issues)
        if replan_res.get("status") != "REPLANNED":
            break

        ir_tree = replan_res["patched_ir"]
        input_defs = build_input_defs(structured_spec)
        result = synthesizer._synthesize_from_ir_tree(
            method_name=method_name,
            ir_tree=ir_tree,
            expected_steps=len(structured_spec.get("steps", [])),
            input_defs=input_defs,
            return_trace=return_trace,
            allow_fallback=allow_fallback,
        )
        if result.get("status") == "FAILED":
            break
        code = result.get("code", "")
        dependencies = result.get("dependencies", []) or []
        resolved_deps = resolve_nuget_deps(dependencies, nuget_client)
        if verifier is not None:
            v_result = verifier.verify(code, dependencies=resolved_deps)
        if spec_auditor is not None:
            try:
                spec_issues = spec_auditor.audit(structured_spec, result)
            except Exception:
                spec_issues = []

    result["spec_issues"] = spec_issues
    result["verification"] = v_result
    result["resolved_dependencies"] = resolved_deps
    return result
