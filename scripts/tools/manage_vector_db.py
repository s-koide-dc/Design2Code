# -*- coding: utf-8 -*-
import argparse
import os
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scripts.sync.sync_method_store import get_expanded_system_methods
from src.code_synthesis.method_harvester import MethodHarvester
from src.code_synthesis.method_store import MethodStore
from src.config.config_manager import ConfigManager
from src.utils.cli_output import emit_error, emit_progress
from src.vector_engine.vector_engine import VectorEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage the AI Method Store & Vector Database")
    parser.add_argument("action", choices=["harvest", "seed", "rebuild", "all"], help="Action to perform")
    parser.add_argument("--root", default=os.getcwd(), help="Workspace root containing config/, resources/, and cache/")
    parser.add_argument(
        "--analysis-path",
        help="Optional override for cache/analysis_output. Used by the harvest action.",
    )
    return parser.parse_args()


def ensure_workspace_dirs(root: Path) -> None:
    (root / "resources").mkdir(parents=True, exist_ok=True)
    (root / "cache").mkdir(parents=True, exist_ok=True)
    (root / "resources" / "vectors" / "vector_db").mkdir(parents=True, exist_ok=True)


def build_config(root: Path) -> ConfigManager:
    ensure_workspace_dirs(root)
    return ConfigManager(workspace_root=root)


def build_store(config_manager: ConfigManager) -> MethodStore:
    vector_engine = VectorEngine(model_path=config_manager.vector_model_path)
    return MethodStore(config_manager, vector_engine=vector_engine)


def harvest_analysis(config_manager: ConfigManager, analysis_path: Path) -> int:
    emit_progress("--- Harvesting from Analysis ---")
    if not analysis_path.exists():
        emit_error(f"エラー: analysis_output が見つかりません: {analysis_path}")
        return 1

    harvester = MethodHarvester(config_manager)
    result = harvester.harvest_from_analysis(str(analysis_path))
    if isinstance(result, dict) and result.get("status") == "success":
        emit_progress(f"Result: {result}")
        return 0

    emit_error(f"エラー: Harvest に失敗しました: {result}")
    return 1


def seed_system(config_manager: ConfigManager) -> int:
    emit_progress("--- Seeding System Methods ---")
    store = build_store(config_manager)
    system_methods = get_expanded_system_methods()
    for method_data in system_methods:
        if "id" not in method_data:
            method_data["id"] = f"sys.{method_data['class'].lower()}.{method_data['name'].lower()}"
        method_data["origin"] = "system"
        if "summary" not in method_data:
            method_data["summary"] = f"Standard library method: {method_data['name']} in {method_data['class']}"
        store.add_method(method_data, overwrite=True)
    store.save()
    emit_progress(f"Seeded {len(system_methods)} system methods.")
    emit_progress(f"Current Store Status: {len(store.items)} methods.")
    return 0


def rebuild_index(config_manager: ConfigManager) -> int:
    emit_progress("--- Rebuilding Index (Vectorization) ---")
    store = build_store(config_manager)

    if store.items and (store.collection.vectors is None or len(store.items) != len(store.collection.vectors)):
        emit_progress("Detected mismatch/missing vectors. Re-indexing...")
        store.load()
    else:
        emit_progress("Index seems consistent. Forcing re-save to be sure.")
        store.save()

    emit_progress(f"Current Store Status: {len(store.items)} methods.")
    return 0


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    config_manager = build_config(root)
    analysis_path = Path(args.analysis_path).resolve() if args.analysis_path else (root / "cache" / "analysis_output")

    actions = {
        "seed": lambda: seed_system(config_manager),
        "harvest": lambda: harvest_analysis(config_manager, analysis_path),
        "rebuild": lambda: rebuild_index(config_manager),
    }

    if args.action == "all":
        for action_name in ["seed", "harvest", "rebuild"]:
            result = actions[action_name]()
            if result != 0:
                return result
        return 0

    return actions[args.action]()


if __name__ == "__main__":
    raise SystemExit(main())
