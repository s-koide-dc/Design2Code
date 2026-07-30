"""Validate declarative, node-targeted semantic mutation cases."""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.design_parser.structured_parser import StructuredDesignParser
from src.design_parser.validator import validate_structured_spec_or_raise
from src.design_parser.compact_step_expander import expand_compact_steps
from src.code_synthesis.code_synthesizer import CodeSynthesizer
from src.code_verification.execution_verifier import ExecutionVerifier
from src.code_verification.runtime_oracle import execute_runtime_oracles
from src.config.config_manager import ConfigManager
from scripts.design.review_design_generation_snapshot import build_review_snapshot

DEFAULT_REGISTRY = ROOT / "resources" / "semantic_mutation_cases.json"


def _set_path(value, path, replacement):
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = replacement


def _mutations(case):
    if "mutations" in case:
        mutations = case["mutations"]
        if not isinstance(mutations, list) or not mutations:
            raise ValueError("mutations must be a non-empty list")
        return mutations
    return [{
        "target_node_id": case.get("target_node_id"),
        "field_path": case.get("field_path"),
        "replacement": case.get("replacement"),
    }]


def _validate_mutation_shape(mutation):
    if not isinstance(mutation, dict):
        raise TypeError("mutation must be an object")
    if not isinstance(mutation.get("target_node_id"), str):
        raise ValueError("mutation requires target_node_id")
    if not isinstance(mutation.get("field_path"), list) or not mutation["field_path"]:
        raise ValueError("mutation requires a non-empty field_path")


def _apply_mutations(spec, case):
    mutated = copy.deepcopy(spec)
    for mutation in _mutations(case):
        _validate_mutation_shape(mutation)
        step = next(item for item in mutated["steps"] if item.get("id") == mutation["target_node_id"])
        _set_path(step, mutation["field_path"], mutation.get("replacement"))
    return mutated


def validate_registry(path: Path) -> list[str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read registry: {exc}"]
    if payload.get("schema_version") != 1 or not isinstance(payload.get("cases"), list):
        return ["schema_version must be 1 and cases must be a list"]
    parser = StructuredDesignParser()
    errors, case_ids = [], set()
    for index, case in enumerate(payload["cases"]):
        prefix = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{prefix} must be an object")
            continue
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            errors.append(f"{prefix}.case_id must be unique and non-empty")
        case_ids.add(case_id)
        design_path = case.get("design_path")
        design = ROOT / design_path if isinstance(design_path, str) else None
        if design is None or not design.is_file():
            errors.append(f"{prefix}.design_path does not exist")
            continue
        try:
            expanded, expansion_errors = expand_compact_steps(design.read_text(encoding="utf-8"))
            if expansion_errors:
                errors.append(f"{prefix}.design_path has invalid compact step syntax")
                continue
            spec = parser.parse_markdown(expanded)
            if case["runtime_oracle_scenario"] not in {item.get("scenario") for item in spec.get("test_cases", [])}:
                errors.append(f"{prefix}.runtime_oracle_scenario is not declared by design")
                continue
            mutated = _apply_mutations(spec, case)
            validate_structured_spec_or_raise(mutated)
        except (KeyError, StopIteration, TypeError, ValueError) as exc:
            errors.append(f"{prefix} cannot apply valid structural mutation: {type(exc).__name__}")
    return errors


def execute_cases(path: Path, case_id: str | None = None) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = [item for item in payload["cases"] if case_id is None or item.get("case_id") == case_id]
    if case_id and not cases:
        return [f"case_id does not exist: {case_id}"]
    parser = StructuredDesignParser()
    snapshots = {}
    errors = []
    with tempfile.TemporaryDirectory(prefix="semantic-mutation-") as temp_dir:
        for case in cases:
            design_path = case["design_path"]
            if design_path not in snapshots:
                args = SimpleNamespace(design=design_path, output_dir=str(Path(temp_dir) / Path(design_path).stem), retry=False, allow_fallback=False, assist_endpoint_url=None, assist_model_id="local-assist", assist_timeout_seconds=60, assist_max_new_tokens=384, fail_on_maintainability=True, run_runtime_oracles=True, assist_policy="on_blocked_only")
                snapshot = build_review_snapshot(args)
                if snapshot["exit_code"] != 0:
                    errors.append(f"{case['case_id']}: baseline generation failed")
                    continue
                snapshots[design_path] = snapshot["payload"]
            baseline = snapshots.get(design_path)
            if baseline is None:
                continue
            spec = copy.deepcopy(parser.parse_design_file(baseline["inferred_design_path"]))
            try:
                spec = _apply_mutations(spec, case)
                synthesizer = CodeSynthesizer(ConfigManager())
                result = synthesizer.synthesize_from_structured_spec(method_name=baseline["module_name"], structured_spec=spec, return_trace=True, allow_fallback=False)
                if result.get("status") != "success":
                    errors.append(f"{case['case_id']}: mutated synthesis did not succeed")
                    continue
                oracle_case = next(item for item in baseline["runtime_oracle"]["cases"] if item.get("scenario") == case["runtime_oracle_scenario"])
                execution = execute_runtime_oracles(source_code=result["code"], module_name=baseline["module_name"], oracle_summary={"cases": [oracle_case]}, verifier=ExecutionVerifier(ConfigManager()), dependencies=baseline.get("resolved_dependencies", []))
                if execution.get("valid") or execution.get("failed") != 1:
                    errors.append(f"{case['case_id']}: mutation did not fail its runtime oracle")
            except (KeyError, StopIteration, TypeError, ValueError) as exc:
                errors.append(f"{case['case_id']}: execution failed: {type(exc).__name__}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate semantic mutation-case registry.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--case-id")
    args = parser.parse_args()
    errors = validate_registry(args.registry)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if args.execute:
        errors = execute_cases(args.registry, args.case_id)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
    print("OK: semantic mutation-case registry is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
