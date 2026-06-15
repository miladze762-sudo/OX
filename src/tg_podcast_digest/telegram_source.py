from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .models import AudioItem


SUPPORTED_AUDIO_EXTENSIONS = {
    ".aac",
    ".flac",
    ".m4a",
    ".mp3",
    ".oga",
    ".ogg",
    ".opus",
    ".wav",
    ".weba",
}


def is_supported_audio(file_name: str | None, mime_type: str | None) -> bool:
    if mime_type and mime_type.lower().startswith("audio/"):
        return True
    if file_name and Path(file_name).suffix.lower() in SUPPORTED_AUDIO_EXTENSIONS:
        return True
    return False


def build_download_path(
    download_dir: Path,
    chat_id: str,
    message_id: int,
    original_name: str | None,
) -> Path:
    name = original_name or "audio"
    suffix = Path(name).suffix
    stem = Path(name).stem if suffix else name
    safe_stem = _sanitize_filename_part(stem) or "audio"
    safe_suffix = suffix.lower() if suffix else ".audio"
    return download_dir / f"{chat_id}_{message_id}_{safe_stem}{safe_suffix}"


class TelegramSourceClient:
    def __init__(self, api_id: int, api_hash: str, source_chat: str, session_path: Path) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        self._source_chat = source_chat
        self._session_path = session_path

    async def setup_login(self) -> None:
        async with self._client() as client:
            await client.start()

    async def list_audio(self, max_messages: int) -> list[AudioItem]:
        items: list[AudioItem] = []
        async with self._client() as client:
            entity = await client.get_entity(self._source_chat)
            async for message in client.iter_messages(entity, limit=max_messages):
                file_name, mime_type = _message_file_info(message)
                if not is_supported_audio(file_name, mime_type):
                    continue
                items.append(
                    AudioItem(
                        chat_id=str(getattr(entity, "id", self._source_chat)),
                        message_id=int(message.id),
                        title=_message_title(message, file_name),
                        message_date=message.date.date().isoformat() if getattr(message, "date", None) else None,
                        file_name=file_name,
                        mime_type=mime_type,
                    )
                )
        return items

    async def download_audio(self, item: AudioItem, download_dir: Path) -> Path:
        download_dir.mkdir(parents=True, exist_ok=True)
        target = build_download_path(download_dir, item.chat_id, item.message_id, item.file_name)
        async with self._client() as client:
            entity = await client.get_entity(self._source_chat)
            message = await client.get_messages(entity, ids=item.message_id)
            downloaded = await client.download_media(message, file=str(target))
        if not downloaded:
            raise RuntimeError(f"Telegram did not return a downloaded path for message {item.message_id}")
        return Path(downloaded)

    def _client(self) -> Any:
        try:
            from telethon import TelegramClient
        except ImportError as exc:
            raise RuntimeError("Telethon is missing. Run: python -m pip install -e .") from exc
        self._session_path.parent.mkdir(parents=True, exist_ok=True)
        return TelegramClient(str(self._session_path), self._api_id, self._api_hash)


def _sanitize_filename_part(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|]+', "_", value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("._- ")


def _message_file_info(message: Any) -> tuple[str | None, str | None]:
    file_obj = getattr(message, "file", None)
    file_name = getattr(file_obj, "name", None)
    mime_type = getattr(file_obj, "mime_type", None)
    if not file_name:
        ext = getattr(file_obj, "ext", None)
        if ext:
            file_name = f"audio{ext}"
    document = getattr(message, "document", None)
    if not mime_type and document is not None:
        mime_type = getattr(document, "mime_type", None)
    return file_name, mime_type


def _message_title(message: Any, file_name: str | None) -> str:
    text = (getattr(message, "message", None) or "").strip()
    if text:
        return text.splitlines()[0][:120]
    return file_name or f"Telegram audio {getattr(message, 'id', '')}".strip()

