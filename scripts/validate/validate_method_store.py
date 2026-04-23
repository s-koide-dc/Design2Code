#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_PATH = os.path.join(ROOT, "resources", "method_store.json")
META_PATH = os.path.join(ROOT, "resources", "method_store_meta.json")

BASE_KEYS = {"id", "name", "class", "tags", "code"}
EXTENDED_KEYS = {
    "return_type",
    "params",
    "definition",
    "has_side_effects",
    "usings",
    "role",
    "origin",
    "summary",
}

ALLOWED_PLACEHOLDERS = {"v0", "v1", "target"}


def load_json(path):
    if not os.path.exists(path):
        return None, f"Missing file: {path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except Exception as exc:
        return None, f"Failed to parse {path}: {exc}"


def _extract_placeholders(text):
    placeholders = []
    if not text:
        return placeholders
    i = 0
    while i < len(text):
        if text[i] == "{":
            j = i + 1
            while j < len(text) and text[j] != "}":
                j += 1
            if j < len(text) and text[j] == "}":
                token = text[i + 1:j]
                if token:
                    placeholders.append(token)
                i = j + 1
                continue
        i += 1
    return placeholders


def validate_method_entry(entry, index, strict=False):
    errors = []
    warnings = []
    missing_base = sorted(BASE_KEYS - set(entry.keys()))
    if missing_base:
        errors.append(f"[{index}] Missing base keys: {', '.join(missing_base)}")
        return errors, warnings
    if strict:
        missing_ext = sorted(EXTENDED_KEYS - set(entry.keys()))
        if missing_ext:
            errors.append(f"[{index}] Missing extended keys: {', '.join(missing_ext)}")
            return errors, warnings
    else:
        missing_ext = sorted(EXTENDED_KEYS - set(entry.keys()))
        if missing_ext:
            warnings.append(f"[{index}] Missing extended keys: {', '.join(missing_ext)}")

    if "params" in entry:
        if not isinstance(entry.get("params"), list):
            errors.append(f"[{index}] params must be a list")
        else:
            for p_idx, param in enumerate(entry.get("params", [])):
                if not isinstance(param, dict):
                    errors.append(f"[{index}] params[{p_idx}] must be an object")
                    continue
                for key in ("name", "type", "role"):
                    if key not in param:
                        msg = f"[{index}] params[{p_idx}] missing '{key}'"
                        if not strict and key == "role":
                            warnings.append(msg)
                        else:
                            errors.append(msg)

    if not isinstance(entry.get("tags"), list):
        errors.append(f"[{index}] tags must be a list")
    if "usings" in entry and not isinstance(entry.get("usings"), list):
        errors.append(f"[{index}] usings must be a list")
    if "has_side_effects" in entry and not isinstance(entry.get("has_side_effects"), bool):
        errors.append(f"[{index}] has_side_effects must be boolean")

    code = entry.get("code") or ""
    placeholders = set(_extract_placeholders(code))
    param_names = {p.get("name") for p in entry.get("params", []) if isinstance(p, dict)}
    extra = sorted(p for p in placeholders if p not in param_names and p not in ALLOWED_PLACEHOLDERS)
    if extra:
        msg = f"[{index}] code has unknown placeholders: {', '.join(extra)}"
        if strict:
            errors.append(msg)
        else:
            warnings.append(msg)

    return errors, warnings


def main():
    errors = []
    warnings = []
    strict = "--strict" in sys.argv

    store_data, err = load_json(STORE_PATH)
    if err:
        errors.append(err)
    meta_data, err = load_json(META_PATH)
    if err:
        errors.append(err)

    if errors:
        print("Method store validation failed:")
        for e in errors:
            print(f" - {e}")
        return 1

    if not isinstance(store_data, dict) or "methods" not in store_data:
        print("Method store validation failed:")
        print(" - method_store.json must be an object with 'methods' list")
        return 1
    methods = store_data.get("methods", [])
    if not isinstance(methods, list):
        print("Method store validation failed:")
        print(" - method_store.json 'methods' must be a list")
        return 1
    if not isinstance(meta_data, list):
        print("Method store validation failed:")
        print(" - method_store_meta.json must be a list")
        return 1

    if len(meta_data) != len(methods):
        errors.append(f"meta length mismatch: methods={len(methods)}, meta={len(meta_data)}")

    ids = []
    for idx, entry in enumerate(methods):
        if not isinstance(entry, dict):
            errors.append(f"[{idx}] method entry must be an object")
            continue
        ids.append(entry.get("id"))
        entry_errors, entry_warnings = validate_method_entry(entry, idx, strict=strict)
        if entry_errors:
            errors.extend(entry_errors)
        if entry_warnings:
            warnings.extend(entry_warnings)

    if len(ids) != len(set(i for i in ids if i)):
        errors.append("duplicate ids detected in method_store.json")

    if errors:
        print("Method store validation failed:")
        for e in errors:
            print(f" - {e}")
        return 1

    if warnings:
        print("Method store validation warnings:")
        for w in warnings:
            print(f" - {w}")
        print("OK: method store validation passed with warnings.")
        return 0

    print("OK: method store validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
