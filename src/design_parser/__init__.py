# -*- coding: utf-8 -*-
from importlib import import_module

__all__ = [
    "StructuredDesignParser",
    "ProjectSpecParser",
    "validate_structured_spec",
    "validate_structured_spec_or_raise",
    "infer_then_freeze_if_needed",
]


_EXPORT_MODULES = {
    "StructuredDesignParser": ".structured_parser",
    "ProjectSpecParser": ".project_spec_parser",
    "validate_structured_spec": ".validator",
    "validate_structured_spec_or_raise": ".validator",
    "infer_then_freeze_if_needed": ".design_inference",
}


def __getattr__(name):
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name, __name__), name)
    globals()[name] = value
    return value
