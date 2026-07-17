"""Create or validate a hash-pinned manifest for optional local assets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.asset_manifest import AssetManifestError, build_manifest, load_requirements, validate_manifest
from src.utils.cli_output import emit_error, emit_json_stdout, emit_progress


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or validate a hash-pinned optional-asset manifest.")
    parser.add_argument("--workspace-root", type=Path, default=ROOT)
    parser.add_argument("--requirements", type=Path, default=ROOT / "config" / "asset_requirements.json")
    parser.add_argument("--manifest", type=Path, default=ROOT / "logs" / "local_asset_manifest.json")
    parser.add_argument("--capability", action="append", dest="capabilities", required=True,
                        help="Capability to include. Repeatable: semantic_pipeline, semantic_method_search, dictionary_search.")
    parser.add_argument("--write-manifest", action="store_true", help="Write a new manifest after hashing local assets.")
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        requirements = load_requirements(args.requirements)
        if args.write_manifest:
            manifest = build_manifest(args.workspace_root, requirements, args.capabilities)
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            result = {"status": "created", "manifest": str(args.manifest), "asset_count": len(manifest["assets"])}
        else:
            manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            mismatches = validate_manifest(args.workspace_root, requirements, manifest, args.capabilities)
            result = {"status": "valid" if not mismatches else "mismatch", "mismatches": mismatches}
    except (AssetManifestError, OSError, json.JSONDecodeError) as exc:
        emit_error(f"Asset manifest validation failed: {exc}")
        return 2

    if args.json:
        emit_json_stdout(result)
    else:
        emit_progress(f"Asset manifest {result['status']}: {result.get('manifest', args.manifest)}")
        for mismatch in result.get("mismatches", []):
            emit_error(mismatch)
    return 0 if result["status"] in {"created", "valid"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
