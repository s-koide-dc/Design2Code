"""Validation and XML rendering for generated .NET package references."""

from __future__ import annotations

from typing import Dict, Iterable, List
from xml.sax.saxutils import escape


class InvalidDependencyError(ValueError):
    """Raised when a generated package reference is not safe to render."""


def normalize_dependencies(dependencies: Iterable[Dict[str, str]] | None) -> List[Dict[str, str]]:
    """Validate dependency fields before they are inserted into a project file."""
    normalized: List[Dict[str, str]] = []
    for dependency in dependencies or []:
        if not isinstance(dependency, dict):
            raise InvalidDependencyError("Dependency entries must be objects.")
        normalized.append({
            "name": _validate_field(dependency.get("name"), "name"),
            "version": _validate_field(dependency.get("version", "*"), "version"),
        })
    return normalized


def render_package_references(dependencies: Iterable[Dict[str, str]] | None) -> str:
    """Render validated dependencies as XML package references."""
    lines = [
        f'    <PackageReference Include="{escape(dep["name"])}" Version="{escape(dep["version"])}" />'
        for dep in normalize_dependencies(dependencies)
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def _validate_field(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidDependencyError(f"Dependency {field_name} must be a non-empty string.")
    value = value.strip()
    if any(char in value for char in '<>&"\'\r\n\t') or any(ord(char) < 0x20 for char in value):
        raise InvalidDependencyError(f"Dependency {field_name} contains forbidden XML characters.")
    return value
