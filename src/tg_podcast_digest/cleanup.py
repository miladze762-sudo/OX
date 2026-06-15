from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path


def cleanup_old_files(paths: list[Path], retention_days: int) -> int:
    if retention_days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    deleted = 0
    for root in paths:
        if not root.exists():
            continue
        for file_path in root.rglob("*"):
            if not file_path.is_file():
                continue
            modified = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
            if modified <= cutoff:
                file_path.unlink()
                deleted += 1
    return deleted

