from __future__ import annotations

from pathlib import Path
from typing import Any


TELEGRAM_TEXT_LIMIT = 4096
TELEGRAM_UPLOAD_LIMIT = 50 * 1024 * 1024


def split_text(text: str, limit: int = TELEGRAM_TEXT_LIMIT) -> list[str]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    if not text:
        return []
    parts: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(line) > limit:
            if current:
                parts.append(current)
                current = ""
            parts.extend(line[index : index + limit] for index in range(0, len(line), limit))
            continue
        if len(current) + len(line) <= limit:
            current += line
        else:
            if current:
                parts.append(current)
            current = line
    if current:
        parts.append(current)
    return parts


class TelegramBotClient:
    def __init__(self, bot_token: str, chat_id: str, session: Any | None = None) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id
        self._session = session or _default_session()

    def send_podcast(
        self,
        title: str,
        summary: str,
        podcast_path: Path,
        notebook_url: str | None = None,
    ) -> list[int]:
        if podcast_path.stat().st_size > TELEGRAM_UPLOAD_LIMIT:
            raise ValueError("Telegram Bot API upload limit is 50 MB for audio files")

        sent_ids: list[int] = []
        audio_caption = title[:1024]
        with podcast_path.open("rb") as audio_file:
            response = self._session.post(
                self._url("sendAudio"),
                data={"chat_id": self._chat_id, "caption": audio_caption},
                files={"audio": (podcast_path.name, audio_file, "audio/mpeg")},
                timeout=120,
            )
        sent_ids.append(_message_id_from_response(response))

        summary_text = summary
        if notebook_url:
            summary_text += f"\n\nNotebookLM: {notebook_url}"
        for chunk in split_text(summary_text):
            response = self._session.post(
                self._url("sendMessage"),
                data={
                    "chat_id": self._chat_id,
                    "text": chunk,
                    "disable_web_page_preview": True,
                },
                timeout=30,
            )
            sent_ids.append(_message_id_from_response(response))
        return sent_ids

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self._bot_token}/{method}"


def _default_session() -> Any:
    try:
        import requests
    except ImportError as exc:
        raise RuntimeError("requests is missing. Run: python -m pip install -e .") from exc
    return requests.Session()


def _message_id_from_response(response: Any) -> int:
    response.raise_for_status()
    payload = response.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram API returned an error: {payload}")
    return int(payload["result"]["message_id"])

