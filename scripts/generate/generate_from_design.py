# -*- coding: utf-8 -*-
"""E2E tool to generate C# code from a .design.md file with Replanner support."""
import argparse
import json
import os
import sys
import copy
import time
from datetime import datetime

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.config.config_manager import ConfigManager
from src.design_parser import StructuredDesignParser, ProjectSpecParser, validate_structured_spec_or_raise, infer_then_freeze_if_needed
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.code_synthesis.synthesis_pipeline import synthesize_structured_spec
from src.code_verification.compilation_verifier import CompilationVerifier
from src.code_verification.execution_verifier import ExecutionVerifier
from src.vector_engine.vector_engine import VectorEngine
from src.replanner.replanner import Replanner
from src.utils.nuget_client import NuGetClient
from src.utils.spec_auditor import SpecAuditor
from src.code_generation.project_generator import ProjectGenerator
from src.log_manager.log_manager import LogManager
from src.action_executor.action_executor import ActionExecutor
from src.refactoring_analyzer.refactoring_analyzer import RefactoringAnalyzer

def main() -> int:
    parser = argparse.ArgumentParser(description="E2E Design-to-Code Generator")
    parser.add_argument("--design", required=True, help="Path to .design.md")
    parser.add_argument("--output", required=False, help="Output .cs path")
    parser.add_argument("--retry", action="store_true", help="Enable Replanner retry loop")
    parser.add_argument("--project", action="store_true", help="Generate multi-file project from Project Spec")
    parser.add_argument("--no-project-audit", action="store_true", help="Skip project audit (SpecAuditor/Replanner)")
    parser.add_argument("--project-audit-only", action="store_true", help="Run project audit (SpecAuditor/Replanner) without generation")
    parser.add_argument("--post-csharp-analyze", action="store_true", help="Run C# Roslyn analysis after project generation")
    parser.add_argument("--post-refactor-analyze", action="store_true", help="Run refactoring analysis after project generation")
    parser.add_argument("--post-exec-verify", action="store_true", help="Run execution verification for single-module generation")
    parser.add_argument("--allow-unsafe", action="store_true", help="Bypass safety policy checks")
    parser.add_argument("--confirm", action="store_true", help="Confirm execution of safety-policy overrides")
    parser.add_argument("--strict-semantics", action="store_true", help="Require explicit intent/ops metadata in design steps")
    parser.add_argument("--allow-fallback", action="store_true", help="Allow UKB fallback pass when synthesis is incomplete")
    args = parser.parse_args()

    if args.strict_semantics:
        os.environ["STRICT_SEMANTICS"] = "1"

    if not os.path.exists(args.design):
        print(f"Error: Design document not found: {args.design}")
        return 1

    config = ConfigManager()
    from src.code_synthesis.method_store import MethodStore
    vector_engine = VectorEngine()
    ms = MethodStore(config, vector_engine=vector_engine)
    synthesizer = CodeSynthesizer(config, method_store=ms)
    sd_parser = StructuredDesignParser(knowledge_base=synthesizer.ukb)
    ps_parser = ProjectSpecParser()
    verifier = CompilationVerifier(config)
    replanner = Replanner(config)
    nc = NuGetClient(config)
    spec_auditor = SpecAuditor(knowledge_base=synthesizer.ukb)

    def is_pascal_case(name: str) -> bool:
        if not name or not isinstance(name, str):
            return False
        if not name[0].isupper():
            return False
        return all(ch.isalnum() for ch in name)

    def validate_output_path(output_path: str, module_name: str, project_rules: dict) -> list:
        errors = []
        if not output_path:
            return errors
        base_name = os.path.splitext(os.path.basename(output_path))[0]
        ext = os.path.splitext(output_path)[1]
        naming = project_rules.get("naming_conventions", {}) if isinstance(project_rules, dict) else {}
        csharp_rules = naming.get("files", {}).get("csharp", {}) if isinstance(naming, dict) else {}
        expected_ext = csharp_rules.get("extension", ".cs")
        if module_name and not is_pascal_case(module_name):
            errors.append(f"Module name must be PascalCase: {module_name}")
        if base_name and not is_pascal_case(base_name):
            errors.append(f"Output file base name must be PascalCase: {base_name}")
        if expected_ext and ext and ext.lower() != expected_ext.lower():
            errors.append(f"Output file extension must be {expected_ext}: {output_path}")
        banned = project_rules.get("banned_patterns", []) if isinstance(project_rules, dict) else []
        for rule in banned:
            pattern = rule.get("pattern")
            if not pattern:
                continue
            if _contains_pattern(output_path, pattern) or _contains_pattern(base_name, pattern):
                desc = rule.get("description", "banned pattern")
                errors.append(f"Output path violates banned pattern ({pattern}): {desc}")
        return errors

    def validate_design_path(design_path: str, module_name: str, project_rules: dict) -> list:
        errors = []
        naming = project_rules.get("naming_conventions", {}) if isinstance(project_rules, dict) else {}
        suffix = naming.get("files", {}).get("design_doc", {}).get("suffix", ".design.md") if isinstance(naming, dict) else ".design.md"
        if suffix and not design_path.endswith(suffix):
            errors.append(f"Design document must end with {suffix}: {design_path}")
        if suffix and design_path.endswith(suffix):
            base_name = os.path.basename(design_path)[:-len(suffix)]
            if module_name and base_name and base_name != module_name:
                errors.append(f"Design document base name must match module name: {base_name} vs {module_name}")
        return errors

    def _looks_like_literal_path(value: str) -> bool:
        if not isinstance(value, str):
            return False
        if "/" in value or "\\" in value:
            return True
        return "." in value

    def validate_spec_paths(spec: dict, project_rules: dict) -> list:
        errors = []
        banned = project_rules.get("banned_patterns", []) if isinstance(project_rules, dict) else []
        if not banned:
            return errors
        module_name = spec.get("module_name", "")
        for rule in banned:
            pattern = rule.get("pattern")
            if not pattern:
                continue
            if module_name and _contains_pattern(module_name, pattern):
                desc = rule.get("description", "banned pattern")
                errors.append(f"Module name violates banned pattern ({pattern}): {desc}")
        steps = spec.get("steps", []) if isinstance(spec.get("steps"), list) else []
        for step in steps:
            if not isinstance(step, dict):
                continue
            roles = step.get("semantic_roles", {}) or {}
            path_val = roles.get("path")
            if isinstance(path_val, str) and _looks_like_literal_path(path_val):
                for rule in banned:
                    pattern = rule.get("pattern")
                    if pattern and _contains_pattern(path_val, pattern):
                        desc = rule.get("description", "banned pattern")
                        errors.append(f"Step {step.get('id')} path violates banned pattern ({pattern}): {desc}")
            source_kind = step.get("source_kind")
            source_ref = step.get("source_ref")
            if source_kind == "file" and isinstance(source_ref, str) and _looks_like_literal_path(source_ref):
                for rule in banned:
                    pattern = rule.get("pattern")
                    if pattern and _contains_pattern(source_ref, pattern):
                        desc = rule.get("description", "banned pattern")
                        errors.append(f"Step {step.get('id')} source_ref violates banned pattern ({pattern}): {desc}")
        return errors

    def enforce_safety_policy(spec: dict, policy: dict, allow_unsafe: bool) -> list:
        if allow_unsafe:
            return []
        destructive = set(policy.get("destructive_intents", []))
        cautionary = set(policy.get("cautionary_intents", []))
        steps = spec.get("steps", []) if isinstance(spec.get("steps"), list) else []
        flagged = []
        for step in steps:
            intent = step.get("intent")
            if intent in destructive or intent in cautionary:
                flagged.append(intent)
        return sorted(set(flagged))

    def validate_safe_commands(spec: dict, policy: dict) -> list:
        errors = []
        safe_commands = set(policy.get("safe_commands", []))
        if not safe_commands:
            return errors
        steps = spec.get("steps", []) if isinstance(spec.get("steps"), list) else []
        for step in steps:
            if not isinstance(step, dict):
                continue
            intent = step.get("intent")
            if intent != "CMD_RUN":
                continue
            semantic_roles = step.get("semantic_roles", {}) or {}
            command = semantic_roles.get("command")
            if not isinstance(command, str) or not command.strip():
                continue
            cmd_name = command.strip().split()[0]
            if cmd_name not in safe_commands:
                errors.append(f"Command not in safety allowlist: {cmd_name}")
        return errors

    def build_method_design_doc(method_name: str, method_spec: dict) -> str:
        if not method_spec:
            return ""
        input_text = str(method_spec.get("input", "")).strip()
        output_text = str(method_spec.get("output", "")).strip()
        core_logic = method_spec.get("core_logic", []) or []
        lines = [f"# {method_name} Design Document", "", "## Purpose", "Auto-generated for audit.", "", "### Input"]
        lines.append(f"- **Description**: {input_text or 'none'}")
        lines.append("")
        lines.append("### Output")
        lines.append(f"- **Description**: {output_text or 'none'}")
        lines.append("")
        lines.append("### Core Logic")
        if core_logic:
            for item in core_logic:
                text = str(item).strip()
                if not text:
                    continue
                if text[0].isdigit() and "." in text:
                    lines.append(text)
                else:
                    lines.append(f"- {text}")
        else:
            lines.append("- (no core logic specified)")
        return "\n".join(lines) + "\n"

    def _clean_type_text(text: str) -> str:
        if not isinstance(text, str):
            return ""
        cleaned = text.replace("`", "")
        for token in ["(", ")", "[", "]"]:
            cleaned = cleaned.replace(token, " ")
        parts = cleaned.split()
        if "or" in parts:
            cleaned = parts[0]
        return cleaned.strip()

    def _extract_output_type(method_spec: dict) -> str:
        output_text = str(method_spec.get("output", "")).strip()
        output_text = _clean_type_text(output_text)
        return output_text or "void"

    def _extract_input_type(method_spec: dict) -> str:
        input_text = str(method_spec.get("input", "")).strip()
        input_text = _clean_type_text(input_text)
        if input_text.lower() in ["none", "void", ""]:
            return ""
        return input_text

    def _extract_sql_from_core(core_logic: list) -> str:
        for line in core_logic or []:
            text = str(line)
            if "`" in text:
                start = text.find("`")
                end = text.rfind("`")
                if start != -1 and end != -1 and end > start:
                    return text[start + 1:end].strip()
        return ""

    def _build_structured_spec_from_method(method_name: str, method_spec: dict, project_spec: dict) -> dict:
        core_logic = method_spec.get("core_logic", []) or []
        output_type = _extract_output_type(method_spec)
        input_type = _extract_input_type(method_spec)
        entity_specs = project_spec.get("spec", {}).get("generation_hints", {}).get("entity_specs", [])
        service_map = {}
        repo_map = {}
        for e in entity_specs:
            svc = e.get("service")
            repo = e.get("repository")
            name = e.get("name")
            if svc and name:
                service_map[svc] = name
            if repo and name:
                repo_map[repo] = name
        class_name = method_name.split(".")[0] if "." in method_name else method_name
        is_service = class_name in service_map
        target_entity = service_map.get(class_name) or repo_map.get(class_name) or "Item"

        step_tokens = method_spec.get("steps", []) or []
        steps = []
        data_sources = []
        step_idx = 1

        def _append_step(text: str, intent: str, side_effect: str, source_kind: str = None, source_ref: str = None, semantic_roles: dict = None):
            nonlocal step_idx
            roles = semantic_roles or {}
            roles.setdefault("audit_only", is_service)
            steps.append({
                "id": f"step_{step_idx}",
                "kind": "ACTION",
                "intent": intent,
                "target_entity": target_entity,
                "input_refs": [f"step_{step_idx-1}"] if step_idx > 1 else [],
                "output_type": output_type,
                "side_effect": side_effect,
                "text": str(text),
                "semantic_roles": roles,
                **({"source_ref": source_ref} if source_ref else {}),
                **({"source_kind": source_kind} if source_kind else {}),
            })
            step_idx += 1

        if core_logic:
            for raw_line in core_logic:
                text = str(raw_line)
                ops = _extract_ops_tag(text)
                if not ops:
                    continue
                if not ops:
                    continue
                intent = "TRANSFORM" if is_service else "GENERAL"
                side_effect = "NONE"
                source_kind = None
                source_ref = None
                semantic_roles = {"ops": ops}
                if any(op in ["repo_insert", "repo_update", "repo_delete"] for op in ops):
                    intent = "PERSIST"
                    side_effect = "DB"
                    source_kind = "db"
                    source_ref = "db_main"
                    if {"id": "db_main", "kind": "db"} not in data_sources:
                        data_sources.append({"id": "db_main", "kind": "db"})
                _append_step(text, intent, side_effect, source_kind=source_kind, source_ref=source_ref, semantic_roles=semantic_roles)
        else:
            for token in step_tokens:
                if not isinstance(token, str):
                    continue
                intent = "GENERAL"
                side_effect = "NONE"
                source_kind = None
                source_ref = None
                semantic_roles = {}
                if token.startswith("service."):
                    if token.endswith("list"):
                        intent = "DISPLAY"
                    elif token.endswith("get"):
                        intent = "TRANSFORM"
                    elif token.endswith("create") or token.endswith("update") or token.endswith("delete"):
                        intent = "TRANSFORM"
                elif token.startswith("repo."):
                    sql_text = _extract_sql_from_core(core_logic)
                    semantic_roles["sql"] = sql_text
                    source_kind = "db"
                    source_ref = "db_main"
                    if {"id": "db_main", "kind": "db"} not in data_sources:
                        data_sources.append({"id": "db_main", "kind": "db"})
                    if token.endswith("fetch_all") or token.endswith("fetch_by_id"):
                        intent = "DATABASE_QUERY"
                    else:
                        intent = "PERSIST"
                    side_effect = "DB"
                _append_step(str(token), intent, side_effect, source_kind=source_kind, source_ref=source_ref, semantic_roles=semantic_roles)

        structured = {
            "module_name": method_name,
            "purpose": "Auto-generated for audit.",
            "inputs": [{"name": "input_1", "description": input_type, "type_format": input_type, "example": ""}] if input_type else [],
            "outputs": [{"name": "output_1", "description": output_type, "type_format": output_type, "example": ""}],
            "steps": steps,
            "constraints": [],
            "test_cases": [],
            "data_sources": data_sources,
        }
        return structured

    def audit_project_methods(project_spec: dict) -> None:
        method_specs = project_spec.get("spec", {}).get("method_specs", {}) if isinstance(project_spec, dict) else {}
        if not method_specs:
            return
        # Default to auditing all methods unless an explicit limit is provided.
        limit_raw = os.environ.get("PROJECT_AUDIT_LIMIT", "0")
        try:
            limit = int(limit_raw)
        except ValueError:
            limit = 10
        if limit < 0:
            limit = 0
        timeout_raw = os.environ.get("PROJECT_AUDIT_TIMEOUT_SEC", "10")
        try:
            timeout_sec = float(timeout_raw)
        except ValueError:
            timeout_sec = 10.0
        if timeout_sec <= 0:
            timeout_sec = 10.0
        offset_raw = os.environ.get("PROJECT_AUDIT_OFFSET", "0")
        try:
            offset = int(offset_raw)
        except ValueError:
            offset = 0
        if offset < 0:
            offset = 0
        print("[*] Running SpecAuditor/Replanner on project methods...")
        audited = 0
        skipped = 0
        for method_name, method_spec in method_specs.items():
            if skipped < offset:
                skipped += 1
                continue
            if limit and audited >= limit:
                print(f"[*] Project audit limit reached ({limit}).")
                break
            start_time = time.time()
            structured_spec = _build_structured_spec_from_method(method_name, method_spec, project_spec)
            try:
                validate_structured_spec_or_raise(structured_spec)
            except Exception as e:
                print(f"[!] Spec validation failed: {method_name}: {e}")
                continue
            result = synthesize_structured_spec(
                synthesizer,
                structured_spec,
                method_name,
                return_trace=True,
                replanner=replanner,
                spec_auditor=spec_auditor,
                allow_retry=True,
                max_retries=3,
            )
            if result.get("status") == "FAILED" or "code" not in result:
                print(f"[!] Synthesis failed during audit: {method_name}")
                continue
            spec_issues = result.get("spec_issues", []) or []
            if spec_issues:
                print(f"[!] Spec alignment issues: {method_name}")
                for issue in spec_issues:
                    print(f"    - {issue}")
            audited += 1
            if time.time() - start_time > timeout_sec:
                print(f"[!] Project audit timeout reached for: {method_name}")
                break

    def build_action_executor() -> ActionExecutor:
        log_manager = LogManager(config_manager=config)
        return ActionExecutor(
            log_manager=log_manager,
            workspace_root=os.getcwd(),
            config_manager=config
        )

    def run_post_generation_checks(output_root: str, project_name: str) -> None:
        if not args.post_csharp_analyze and not args.post_refactor_analyze:
            return
        executor = build_action_executor()

        if args.post_csharp_analyze:
            context = {"session_id": "postgen", "analysis": {}, "plan": {}}
            project_file = os.path.join(output_root, f"{project_name}.csproj")
            rel_path = os.path.relpath(project_file, os.getcwd())
            result = executor._analyze_csharp(context, {"filename": rel_path})
            status = result.get("action_result", {}).get("status", "error")
            message = result.get("action_result", {}).get("message", "")
            if status == "success":
                print("[+] C# analysis completed.")
            else:
                print(f"[!] C# analysis failed: {message}")

        if args.post_refactor_analyze:
            analyzer = RefactoringAnalyzer(
                workspace_root=os.getcwd(),
                log_manager=executor.log_manager,
                action_executor=executor
            )
            ref_result = analyzer.analyze_project(output_root, "csharp")
            if ref_result.get("status") == "success":
                smell_count = len(ref_result.get("code_smells", []))
                print(f"[+] Refactoring analysis completed. Smells: {smell_count}")
            else:
                print(f"[!] Refactoring analysis failed: {ref_result.get('message')}")

    print(f"[*] Parsing design: {args.design}")

    def _contains_pattern(text: str, pattern: str) -> bool:
        if not isinstance(text, str) or not isinstance(pattern, str):
            return False
        return pattern in text

    def _extract_ops_tag(text: str) -> list[str]:
        if not isinstance(text, str):
            return []
        start = text.lower().find("[ops:")
        if start == -1:
            return []
        end = text.find("]", start)
        if end == -1:
            return []
        raw = text[start + len("[ops:"):end]
        return [o.strip().lower() for o in raw.split(",") if o.strip()]

    if args.project_audit_only:
        project_spec = ps_parser.parse_file(args.design)
        audit_project_methods(project_spec)
        return 0

    if args.project:
        project_spec = ps_parser.parse_file(args.design)
        project_name = project_spec.get("project_name") or "GeneratedProject"

        project_rules = config.get_project_rules() or {}
        rule_errors = []
        rule_errors.extend(validate_design_path(args.design, project_name, project_rules))
        if rule_errors:
            print("[!] Project rule violations detected:")
            for err in rule_errors:
                print(f"    - {err}")
            return 1

        output_root = args.output or os.path.join(os.getcwd(), project_name)
        if args.output and os.path.splitext(args.output)[1]:
            output_root = os.path.splitext(args.output)[0]
        generator = ProjectGenerator()
        generator.generate(project_spec, output_root)
        if not args.no_project_audit:
            audit_project_methods(project_spec)
        run_post_generation_checks(output_root, project_name)
        build_result = verifier.verify_project(output_root, project_name=project_name)
        if not build_result.get("valid", False):
            print("[!] Project compilation failed:")
            for err in build_result.get("errors", []):
                code = err.get("code", "")
                msg = err.get("message", "")
                if code:
                    print(f"    - {code}: {msg}")
                else:
                    print(f"    - {msg}")
            return 1
        print(f"[+] Project generated at {output_root}")
        return 0

    inference_result = infer_then_freeze_if_needed(
        args.design,
        config_manager=config,
        vector_engine=vector_engine,
    )
    if inference_result.get("status") == "blocked":
        print("[!] Design inference blocked generation:")
        for issue in inference_result.get("issues", []):
            step_idx = issue.get("step_index")
            reason = issue.get("reason")
            detail = issue.get("detail")
            print(f"    - step {step_idx}: {reason} ({detail})")
        return 1

    inferred_design_path = inference_result.get("output_path") or args.design
    spec = sd_parser.parse_design_file(inferred_design_path)
    validate_structured_spec_or_raise(spec)
    
    module_name = spec.get("module_name", "GeneratedModule")
    output_path = args.output or f"{module_name}.cs"

    # P0: Safety policy enforcement
    safety_policy = config.get_safety_policy() or {}
    flagged_intents = enforce_safety_policy(spec, safety_policy, args.allow_unsafe)
    if flagged_intents:
        print("[!] Safety policy violation detected. Blocked intents:")
        for intent in flagged_intents:
            print(f"    - {intent}")
        print("[!] Use --allow-unsafe to bypass this check.")
        return 1
    if args.allow_unsafe and not args.confirm:
        print("[!] Safety policy override requested, but confirmation is missing.")
        print("[!] Re-run with --confirm to proceed.")
        return 1
    safe_cmd_errors = validate_safe_commands(spec, safety_policy)
    if safe_cmd_errors:
        print("[!] Safety policy violation detected (commands):")
        for err in safe_cmd_errors:
            print(f"    - {err}")
        print("[!] Update safety_policy.json or avoid unsafe commands.")
        return 1

    # P0: Project rules enforcement
    project_rules = config.get_project_rules() or {}
    rule_errors = []
    rule_errors.extend(validate_design_path(args.design, module_name, project_rules))
    rule_errors.extend(validate_output_path(output_path, module_name, project_rules))
    rule_errors.extend(validate_spec_paths(spec, project_rules))
    if rule_errors:
        print("[!] Project rule violations detected:")
        for err in rule_errors:
            print(f"    - {err}")
        return 1

    print(f"[*] Starting synthesis for {module_name}...")
    result = synthesize_structured_spec(
        synthesizer,
        spec,
        module_name,
        return_trace=True,
        verifier=verifier,
        replanner=replanner,
        spec_auditor=spec_auditor,
        nuget_client=nc,
        allow_retry=args.retry,
        allow_fallback=args.allow_fallback,
        max_retries=3,
    )

    if result.get("status") == "FAILED":
        print(f"[!] Synthesis failed: {result.get('code')}")
        return 1

    code = result.get("code", "")
    v_result = result.get("verification", {"valid": True, "errors": []})
    resolved_deps = result.get("resolved_dependencies", [])
    spec_issues = result.get("spec_issues", []) or []

    if args.post_exec_verify:
        exec_verifier = ExecutionVerifier(config)
        exec_result = exec_verifier.run_and_capture(code, module_name, dependencies=resolved_deps)
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = os.path.join(log_dir, f"exec_verify_{module_name}_{stamp}.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("=== Execution Verification ===\n")
            f.write(f"module: {module_name}\n")
            f.write(f"success: {exec_result.get('success')}\n")
            if exec_result.get("error_type"):
                f.write(f"error_type: {exec_result.get('error_type')}\n")
            if exec_result.get("error"):
                f.write(f"error: {exec_result.get('error')}\n")
            if exec_result.get("exception"):
                f.write(f"exception: {exec_result.get('exception')}\n")
            if exec_result.get("stdout"):
                f.write("\n--- stdout ---\n")
                f.write(exec_result.get("stdout"))
            if exec_result.get("stderr"):
                f.write("\n--- stderr ---\n")
                f.write(exec_result.get("stderr"))
        if exec_result.get("success"):
            print("[+] Execution verification succeeded.")
        else:
            err_type = exec_result.get("error_type") or exec_result.get("error")
            print(f"[!] Execution verification failed: {err_type}")
        print(f"[*] Execution verification log saved: {log_path}")

    if resolved_deps:
        print("[*] Resolved NuGet dependencies:")
        for dep in resolved_deps:
            print(f"    - {dep.get('name')} ({dep.get('version', '*')})")
    else:
        print("[*] Resolved NuGet dependencies: none")

    if spec_issues:
        print("[!] Spec alignment issues detected:")
        for issue in spec_issues:
            print(f"    - {issue}")
        blocking_spec = any(str(issue).startswith("SPEC_INPUT_LINK_UNUSED") for issue in spec_issues)
        if blocking_spec and not args.retry:
            print("[!] Blocking issue detected: SPEC_INPUT_LINK_UNUSED")
            return 1

    if "// TODO" in code:
        print("[!] Warning: Generated code still contains TODOs after retries.")
    elif v_result.get("valid", False):
        print("[+] Synthesis successful!")

    final_spec_issues = result.get("spec_issues", []) or []
    if any(str(issue).startswith("SPEC_INPUT_LINK_UNUSED") for issue in final_spec_issues):
        print("[!] Blocking issue detected after retries: SPEC_INPUT_LINK_UNUSED")
        return 1

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(code)
    
    print(f"[+] Result saved to {output_path}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
