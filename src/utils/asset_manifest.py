"""Create and validate local, hash-pinned optional asset manifests."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any


class AssetManifestError(ValueError):
    """Raised when an asset requirement or manifest is invalid."""


def load_requirements(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AssetManifestError(f"Cannot read asset requirements: {path}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise AssetManifestError("Asset requirements must use schema_version 1")
    if not isinstance(data.get("capabilities"), dict):
        raise AssetManifestError("Asset requirements must define capabilities")
    return data


def _capability_assets(requirements: dict[str, Any], requested: list[str]) -> list[dict[str, str]]:
    capabilities = requirements["capabilities"]
    selected: set[str] = set()
    active: set[str] = set()

    def visit(name: str) -> None:
        if name in selected:
            return
        if name in active:
            raise AssetManifestError(f"Cyclic capability dependency: {name}")
        definition = capabilities.get(name)
        if not isinstance(definition, dict):
            raise AssetManifestError(f"Unknown capability: {name}")
        active.add(name)
        dependencies = definition.get("requires", [])
        if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
            raise AssetManifestError(f"Invalid requires list for capability: {name}")
        for dependency in dependencies:
            visit(dependency)
        active.remove(name)
        selected.add(name)

    for capability in requested:
        visit(capability)

    assets: list[dict[str, str]] = []
    asset_ids: set[str] = set()
    for capability in sorted(selected):
        definition = capabilities[capability]
        entries = definition.get("assets", [])
        if not isinstance(entries, list):
            raise AssetManifestError(f"Invalid assets list for capability: {capability}")
        for entry in entries:
            if not isinstance(entry, dict):
                raise AssetManifestError(f"Invalid asset entry for capability: {capability}")
            asset_id = entry.get("id")
            asset_path = entry.get("path")
            if not isinstance(asset_id, str) or not isinstance(asset_path, str) or not asset_id or not asset_path:
                raise AssetManifestError(f"Asset entries require non-empty id and path: {capability}")
            if asset_id in asset_ids:
                raise AssetManifestError(f"Duplicate asset id: {asset_id}")
            asset_ids.add(asset_id)
            assets.append({"id": asset_id, "path": asset_path})
    return assets


def _workspace_file(workspace_root: Path, relative_path: str) -> Path:
    candidate = (workspace_root / relative_path).resolve()
    try:
        candidate.relative_to(workspace_root.resolve())
    except ValueError as exc:
        raise AssetManifestError(f"Asset path escapes workspace: {relative_path}") from exc
    if not candidate.is_file():
        raise AssetManifestError(f"Required asset is missing: {relative_path}")
    return candidate


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_manifest(workspace_root: Path, requirements: dict[str, Any], capabilities: list[str]) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    assets = _capability_assets(requirements, capabilities)
    records = []
    for asset in assets:
        path = _workspace_file(workspace_root, asset["path"])
        records.append({
            "id": asset["id"],
            "path": asset["path"],
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        })
    return {
        "schema_version": 1,
        "requirements_schema_version": requirements["schema_version"],
        "created_at_utc": datetime.now(UTC).isoformat(),
        "capabilities": capabilities,
        "assets": records,
    }


def validate_manifest(workspace_root: Path, requirements: dict[str, Any], manifest: dict[str, Any], capabilities: list[str]) -> list[str]:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise AssetManifestError("Asset manifest must use schema_version 1")
    if manifest.get("requirements_schema_version") != requirements["schema_version"]:
        raise AssetManifestError("Asset manifest was created for a different requirements schema")

    expected = {asset["id"]: asset["path"] for asset in _capability_assets(requirements, capabilities)}
    actual = manifest.get("assets")
    if not isinstance(actual, list):
        raise AssetManifestError("Asset manifest must define assets")
    actual_by_id = {entry.get("id"): entry for entry in actual if isinstance(entry, dict) and isinstance(entry.get("id"), str)}
    if set(actual_by_id) != set(expected):
        raise AssetManifestError("Asset manifest does not match the selected capability assets")

    mismatches: list[str] = []
    for asset_id, relative_path in expected.items():
        record = actual_by_id[asset_id]
        if record.get("path") != relative_path:
            mismatches.append(f"{asset_id}: path changed")
            continue
        path = _workspace_file(workspace_root, relative_path)
        if record.get("size_bytes") != path.stat().st_size:
            mismatches.append(f"{asset_id}: size changed")
            continue
        if record.get("sha256") != _sha256(path):
            mismatches.append(f"{asset_id}: SHA-256 changed")
    return mismatches
