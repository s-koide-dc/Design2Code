# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List


_REQUIRED_TOP_LEVEL = [
    "module_name",
    "purpose",
    "inputs",
    "outputs",
    "steps",
    "constraints",
    "test_cases",
    "data_sources",
]

_ALLOWED_KINDS = {"ACTION", "CONDITION", "LOOP", "ELSE", "END"}
_ALLOWED_EFFECTS = {"NONE", "IO", "NETWORK", "DB"}
_ALLOWED_SOURCE_KINDS = {"db", "http", "file", "memory", "env", "stdin"}
def _is_step_id(val: str) -> bool:
    if not isinstance(val, str):
        return False
    if not val.startswith("step_"):
        return False
    suffix = val[len("step_"):]
    return suffix.isdigit()

def _is_tc_id(val: str) -> bool:
    if not isinstance(val, str):
        return False
    if not val.startswith("tc_"):
        return False
    suffix = val[len("tc_"):]
    return suffix.isdigit()

def _is_source_id(val: str) -> bool:
    if not isinstance(val, str) or not val:
        return False
    return all(ch.isalnum() or ch == "_" for ch in val)


class StructuredSpecValidationError(ValueError):
    pass


def validate_structured_spec(spec: Dict[str, Any]) -> List[str]:
    """Return a list of validation errors. Empty list means valid."""
    errors: List[str] = []

    for key in _REQUIRED_TOP_LEVEL:
        if key not in spec:
            errors.append(f"missing top-level key: {key}")

    if errors:
        return errors

    if not isinstance(spec.get("module_name"), str) or not spec["module_name"].strip():
        errors.append("module_name must be a non-empty string")
    if not isinstance(spec.get("purpose"), str) or not spec["purpose"].strip():
        errors.append("purpose must be a non-empty string")

    for key in ["inputs", "outputs", "steps", "constraints", "test_cases", "data_sources"]:
        if not isinstance(spec.get(key), list):
            errors.append(f"{key} must be a list")

    source_ids: List[str] = []
    source_kind_map: Dict[str, str] = {}
    if isinstance(spec.get("data_sources"), list):
        for i, ds in enumerate(spec["data_sources"], start=1):
            if not isinstance(ds, dict):
                errors.append(f"data_sources[{i}] must be an object")
                continue
            for required in ["id", "kind"]:
                if required not in ds:
                    errors.append(f"data_sources[{i}] missing key: {required}")
            ds_id = ds.get("id")
            ds_kind = ds.get("kind")
            if isinstance(ds_id, str):
                source_ids.append(ds_id)
                if not _is_source_id(ds_id):
                    errors.append(f"data_sources[{i}] id format is invalid: {ds_id}")
            else:
                errors.append(f"data_sources[{i}] id must be string")
            if ds_kind not in _ALLOWED_SOURCE_KINDS:
                errors.append(f"data_sources[{i}] kind must be one of {sorted(_ALLOWED_SOURCE_KINDS)}")
            if isinstance(ds_id, str) and isinstance(ds_kind, str):
                source_kind_map[ds_id] = ds_kind

    if len(source_ids) != len(set(source_ids)):
        errors.append("data source ids must be unique")

    step_ids: List[str] = []
    if isinstance(spec.get("steps"), list):
        for i, step in enumerate(spec["steps"], start=1):
            if not isinstance(step, dict):
                errors.append(f"steps[{i}] must be an object")
                continue

            for required in ["id", "kind", "intent", "target_entity", "input_refs", "output_type", "side_effect", "text"]:
                if required not in step:
                    errors.append(f"steps[{i}] missing key: {required}")

            step_id = step.get("id")
            if isinstance(step_id, str):
                step_ids.append(step_id)
                if not _is_step_id(step_id):
                    errors.append(f"steps[{i}] id format is invalid: {step_id}")
            else:
                errors.append(f"steps[{i}] id must be string")

            kind = step.get("kind")
            if kind not in _ALLOWED_KINDS:
                errors.append(f"steps[{i}] kind must be one of {sorted(_ALLOWED_KINDS)}")

            side_effect = step.get("side_effect")
            if side_effect not in _ALLOWED_EFFECTS:
                errors.append(f"steps[{i}] side_effect must be one of {sorted(_ALLOWED_EFFECTS)}")

            if kind not in ["ELSE", "END"]:
                if not isinstance(step.get("text"), str) or not step["text"].strip():
                    errors.append(f"steps[{i}] text must be a non-empty string")

            input_refs = step.get("input_refs")
            if not isinstance(input_refs, list) or any(not isinstance(x, str) for x in input_refs):
                errors.append(f"steps[{i}] input_refs must be list[str]")

            depends_on = step.get("depends_on")
            if depends_on is not None and (not isinstance(depends_on, list) or any(not isinstance(x, str) for x in depends_on)):
                errors.append(f"steps[{i}] depends_on must be list[str]")

            source_ref = step.get("source_ref")
            source_kind = step.get("source_kind")
            if source_ref is not None and not isinstance(source_ref, str):
                errors.append(f"steps[{i}] source_ref must be string")
            if isinstance(source_ref, str) and source_ref not in source_kind_map:
                errors.append(f"steps[{i}] source_ref references unknown data source id: {source_ref}")

            if source_kind is not None and source_kind not in _ALLOWED_SOURCE_KINDS:
                errors.append(f"steps[{i}] source_kind must be one of {sorted(_ALLOWED_SOURCE_KINDS)}")

            intent = step.get("intent")
            if intent == "FETCH":
                if source_kind != "file":
                    if not isinstance(source_ref, str) or source_ref not in source_kind_map:
                        errors.append("steps[{i}] intent=FETCH requires valid source_ref".format(i=i))
                if not isinstance(source_kind, str) or source_kind not in _ALLOWED_SOURCE_KINDS:
                    errors.append("steps[{i}] intent=FETCH requires valid source_kind".format(i=i))

            if intent == "DATABASE_QUERY":
                semantic_roles = step.get("semantic_roles") if isinstance(step.get("semantic_roles"), dict) else {}
                sql_text = semantic_roles.get("sql")
                has_sql = isinstance(sql_text, str) and bool(sql_text.strip())
                is_db_ref = isinstance(source_ref, str) and source_kind_map.get(source_ref) == "db"
                if not is_db_ref:
                    errors.append("steps[{i}] intent=DATABASE_QUERY requires source_ref(kind=db)".format(i=i))
                if not isinstance(source_kind, str) or source_kind != "db":
                    errors.append("steps[{i}] intent=DATABASE_QUERY requires source_kind=db".format(i=i))
                if not has_sql:
                    errors.append("steps[{i}] intent=DATABASE_QUERY requires semantic_roles.sql (e.g. SQL '...')".format(i=i))

    if len(step_ids) != len(set(step_ids)):
        errors.append("step ids must be unique")

    step_id_set = set(step_ids)
    if isinstance(spec.get("steps"), list):
        for i, step in enumerate(spec["steps"], start=1):
            for ref in step.get("input_refs", []):
                if ref not in step_id_set:
                    errors.append(f"steps[{i}] references unknown step id: {ref}")
            for ref in step.get("depends_on", []):
                if ref not in step_id_set:
                    errors.append(f"steps[{i}] depends_on unknown step id: {ref}")

    tc_ids: List[str] = []
    if isinstance(spec.get("test_cases"), list):
        for i, tc in enumerate(spec["test_cases"], start=1):
            if not isinstance(tc, dict):
                errors.append(f"test_cases[{i}] must be an object")
                continue
            for required in ["id", "type", "scenario", "input", "expected"]:
                if required not in tc:
                    errors.append(f"test_cases[{i}] missing key: {required}")
            tc_id = tc.get("id")
            if isinstance(tc_id, str):
                tc_ids.append(tc_id)
                if not _is_tc_id(tc_id):
                    errors.append(f"test_cases[{i}] id format is invalid: {tc_id}")
            else:
                errors.append(f"test_cases[{i}] id must be string")

    if len(tc_ids) != len(set(tc_ids)):
        errors.append("test case ids must be unique")

    return errors


def validate_structured_spec_or_raise(spec: Dict[str, Any]) -> None:
    errors = validate_structured_spec(spec)
    if errors:
        raise StructuredSpecValidationError("; ".join(errors))
