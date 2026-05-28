# -*- coding: utf-8 -*-
"""
Prune backup files under backup/ based on retention rules.
Default policy:
- Keep latest 30 days
- Keep latest 50 files per source (basename), whichever is smaller
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.utils.cli_output import emit_error, emit_progress

def _parse_timestamp(name: str) -> datetime | None:
    # Expected: <basename>.<YYYYMMDD_HHMMSS>.bak
    parts = name.split(".")
    if len(parts) < 3:
        return None
    ts_part = parts[-2]
    try:
        return datetime.strptime(ts_part, "%Y%m%d_%H%M%S")
    except ValueError:
        return None

def _group_backups(files: list[tuple[str, datetime]]) -> dict[str, list[tuple[str, datetime]]]:
    groups: dict[str, list[tuple[str, datetime]]] = {}
    for path, ts in files:
        base = os.path.basename(path)
        # base without timestamp and .bak
        parts = base.split(".")
        if len(parts) < 3:
            continue
        source_name = ".".join(parts[:-2])
        groups.setdefault(source_name, []).append((path, ts))
    return groups

def prune_backups(root: str, days: int, max_per_source: int, dry_run: bool) -> int:
    backup_dir = os.path.join(root, "backup")
    if not os.path.isdir(backup_dir):
        emit_error(f"エラー: backup ディレクトリが見つかりません: {backup_dir}")
        return 1

    now = datetime.now()
    cutoff = now - timedelta(days=days)

    candidates: list[tuple[str, datetime]] = []
    for entry in os.scandir(backup_dir):
        if not entry.is_file():
            continue
        if not entry.name.endswith(".bak"):
            continue
        ts = _parse_timestamp(entry.name)
        if not ts:
            continue
        candidates.append((entry.path, ts))

    groups = _group_backups(candidates)
    removed = 0

    for source, items in groups.items():
        items_sorted = sorted(items, key=lambda x: x[1], reverse=True)
        # Enforce max_per_source
        keep_set = set(p for p, _ in items_sorted[:max_per_source])
        for path, ts in items_sorted:
            if ts >= cutoff and path in keep_set:
                continue
            if dry_run:
                emit_progress(f"[DRYRUN] remove {path}")
            else:
                try:
                    os.remove(path)
                    removed += 1
                except OSError as e:
                    emit_error(f"警告: バックアップ削除に失敗しました: {path}: {e}")

    emit_progress(f"[+] prune complete. removed={removed}")
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(description="Prune backup files under backup/")
    parser.add_argument("--days", type=int, default=30, help="Retention days (default: 30)")
    parser.add_argument("--max-per-source", type=int, default=50, help="Max backups per source file (default: 50)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be removed")
    parser.add_argument("--root", default=os.getcwd(), help="Project root containing backup/ (default: current working directory)")
    args = parser.parse_args()

    root = os.path.abspath(args.root)
    return prune_backups(root, args.days, args.max_per_source, args.dry_run)

if __name__ == "__main__":
    raise SystemExit(main())
