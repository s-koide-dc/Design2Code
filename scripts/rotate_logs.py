from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile


def rotate_logs(
    log_dir: str | Path = "logs",
    file_prefix: str = "pipeline",
    retention_days: int = 7,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(retention_days, int) or isinstance(retention_days, bool):
        raise TypeError("retention_days must be an integer")
    if retention_days < 0:
        raise ValueError("retention_days must be non-negative")
    if not file_prefix:
        raise ValueError("file_prefix must not be empty")

    root = Path(log_dir)
    if not root.exists():
        return {
            "status": "success",
            "archived_files": [],
            "archive_path": None,
        }
    if not root.is_dir():
        raise NotADirectoryError(str(root))

    reference_time = now or datetime.now()
    cutoff = reference_time - timedelta(days=retention_days)
    candidates = []
    for extension in (".log", ".json"):
        for path in root.glob(f"{file_prefix}_*{extension}"):
            modified_at = datetime.fromtimestamp(path.stat().st_mtime)
            if modified_at < cutoff:
                candidates.append(path)

    candidates = sorted(set(candidates), key=lambda path: path.name)
    if not candidates:
        return {
            "status": "success",
            "archived_files": [],
            "archive_path": None,
        }

    archive_dir = root / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / (
        f"{file_prefix}_{reference_time.strftime('%Y%m%d_%H%M%S_%f')}.zip"
    )
    with ZipFile(archive_path, mode="x", compression=ZIP_DEFLATED) as archive:
        for path in candidates:
            archive.write(path, arcname=path.name)

    for path in candidates:
        path.unlink()

    return {
        "status": "success",
        "archived_files": [path.name for path in candidates],
        "archive_path": str(archive_path),
    }
