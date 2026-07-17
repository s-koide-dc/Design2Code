import json
import tempfile
import unittest
from pathlib import Path

from src.utils.asset_manifest import AssetManifestError, build_manifest, load_requirements, validate_manifest


class TestAssetManifest(unittest.TestCase):
    def _requirements(self) -> dict:
        return {
            "schema_version": 1,
            "capabilities": {
                "vectors": {"assets": [{"id": "model", "path": "resources/model.bin"}]},
                "search": {"requires": ["vectors"], "assets": [{"id": "index", "path": "resources/index.bin"}]},
            },
        }

    def test_builds_and_validates_manifest_with_transitive_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resources = root / "resources"
            resources.mkdir()
            (resources / "model.bin").write_bytes(b"model")
            (resources / "index.bin").write_bytes(b"index")

            manifest = build_manifest(root, self._requirements(), ["search"])

            self.assertEqual(["index", "model"], sorted(asset["id"] for asset in manifest["assets"]))
            self.assertEqual([], validate_manifest(root, self._requirements(), manifest, ["search"]))

    def test_reports_hash_mismatch_after_asset_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resources = root / "resources"
            resources.mkdir()
            model = resources / "model.bin"
            model.write_bytes(b"model")
            manifest = build_manifest(root, self._requirements(), ["vectors"])
            model.write_bytes(b"changed")

            self.assertEqual(["model: size changed"], validate_manifest(root, self._requirements(), manifest, ["vectors"]))

    def test_rejects_paths_outside_workspace(self):
        requirements = {"schema_version": 1, "capabilities": {"unsafe": {"assets": [{"id": "outside", "path": "../outside.bin"}]}}}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(AssetManifestError) as raised:
                build_manifest(Path(directory), requirements, ["unsafe"])
            self.assertEqual("Asset path escapes workspace: ../outside.bin", str(raised.exception))

    def test_load_requirements_rejects_wrong_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset_requirements.json"
            path.write_text(json.dumps({"schema_version": 2, "capabilities": {}}), encoding="utf-8")
            with self.assertRaises(AssetManifestError):
                load_requirements(path)
