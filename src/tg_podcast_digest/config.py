from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    tg_api_id: int
    tg_api_hash: str
    tg_source_chat: str
    notebooklm_storage_path: Path
    telegram_bot_token: str
    telegram_output_chat_id: str
    database_path: Path = Path("data/podcast_digest.sqlite3")
    tg_session_path: Path = Path("data/telegram.session")
    download_dir: Path = Path("downloads")
    converted_dir: Path = Path("output/converted")
    export_dir: Path = Path("output/exports")
    ffmpeg_path: str = "ffmpeg"
    max_messages_per_run: int = 10
    local_retention_days: int = 30


REQUIRED_KEYS = [
    "TG_API_ID",
    "TG_API_HASH",
    "TG_SOURCE_CHAT",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_OUTPUT_CHAT_ID",
    "NOTEBOOKLM_STORAGE_PATH",
]


def load_settings(env_path: str | Path = ".env") -> Settings:
    values = _read_env_file(Path(env_path))
    values.update(os.environ)
    missing = [key for key in REQUIRED_KEYS if not str(values.get(key, "")).strip()]
    if missing:
        raise ValueError("Missing required config values: " + ", ".join(missing))

    return Settings(
        tg_api_id=int(values["TG_API_ID"]),
        tg_api_hash=values["TG_API_HASH"],
        tg_source_chat=values["TG_SOURCE_CHAT"],
        notebooklm_storage_path=Path(values["NOTEBOOKLM_STORAGE_PATH"]),
        telegram_bot_token=values["TELEGRAM_BOT_TOKEN"],
        telegram_output_chat_id=values["TELEGRAM_OUTPUT_CHAT_ID"],
        database_path=Path(values.get("DATABASE_PATH", "data/podcast_digest.sqlite3")),
        tg_session_path=Path(values.get("TG_SESSION_PATH", "data/telegram.session")),
        download_dir=Path(values.get("DOWNLOAD_DIR", "downloads")),
        converted_dir=Path(values.get("CONVERTED_DIR", "output/converted")),
        export_dir=Path(values.get("EXPORT_DIR", "output/exports")),
        ffmpeg_path=values.get("FFMPEG_PATH", "ffmpeg"),
        max_messages_per_run=int(values.get("MAX_MESSAGES_PER_RUN", "10")),
        local_retention_days=int(values.get("LOCAL_RETENTION_DAYS", "30")),
    )


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip().lstrip("\ufeff")] = _strip_quotes(value.strip())
    return values


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value

