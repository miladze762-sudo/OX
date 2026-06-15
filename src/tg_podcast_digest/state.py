from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class MessageRecord:
    chat_id: str
    message_id: int
    title: str
    message_date: str | None
    status: str
    source_path: Path | None
    converted_path: Path | None
    notebook_id: str | None
    notebook_url: str | None
    summary: str | None
    podcast_path: Path | None
    telegram_message_ids: list[int]
    error: str | None


class StateStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def initialize(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        chat_id TEXT NOT NULL,
                        message_id INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        message_date TEXT,
                        status TEXT NOT NULL,
                        source_path TEXT,
                        converted_path TEXT,
                        notebook_id TEXT,
                        notebook_url TEXT,
                        summary TEXT,
                        podcast_path TEXT,
                        telegram_message_ids TEXT,
                        error TEXT,
                        claimed_at TEXT,
                        downloaded_at TEXT,
                        converted_at TEXT,
                        notebook_at TEXT,
                        summary_at TEXT,
                        podcast_at TEXT,
                        sent_at TEXT,
                        failed_at TEXT,
                        PRIMARY KEY (chat_id, message_id)
                    )
                    """
                )

    def claim_message(self, chat_id: str, message_id: int, title: str, message_date: str | None) -> bool:
        self.initialize()
        with closing(self._connect()) as db:
            with db:
                row = db.execute(
                    "SELECT status FROM messages WHERE chat_id = ? AND message_id = ?",
                    (chat_id, message_id),
                ).fetchone()
                if row and row["status"] == "processed":
                    return False
                db.execute(
                    """
                    INSERT INTO messages (
                        chat_id, message_id, title, message_date, status, claimed_at, error
                    )
                    VALUES (?, ?, ?, ?, 'processing', ?, NULL)
                    ON CONFLICT(chat_id, message_id) DO UPDATE SET
                        title = excluded.title,
                        message_date = excluded.message_date,
                        status = 'processing',
                        claimed_at = excluded.claimed_at,
                        error = NULL
                    """,
                    (chat_id, message_id, title, message_date, _utcnow()),
                )
                return True

    def mark_downloaded(self, chat_id: str, message_id: int, source_path: Path) -> None:
        self._update(chat_id, message_id, "downloaded", "source_path", str(source_path), "downloaded_at")

    def mark_converted(self, chat_id: str, message_id: int, converted_path: Path) -> None:
        self._update(chat_id, message_id, "converted", "converted_path", str(converted_path), "converted_at")

    def mark_notebook_ready(self, chat_id: str, message_id: int, notebook_id: str, notebook_url: str) -> None:
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    UPDATE messages
                    SET status = 'notebook_ready', notebook_id = ?, notebook_url = ?, notebook_at = ?
                    WHERE chat_id = ? AND message_id = ?
                    """,
                    (notebook_id, notebook_url, _utcnow(), chat_id, message_id),
                )

    def mark_summary_ready(self, chat_id: str, message_id: int, summary: str) -> None:
        self._update(chat_id, message_id, "summary_ready", "summary", summary, "summary_at")

    def mark_podcast_ready(self, chat_id: str, message_id: int, podcast_path: Path) -> None:
        self._update(chat_id, message_id, "podcast_ready", "podcast_path", str(podcast_path), "podcast_at")

    def mark_sent(self, chat_id: str, message_id: int, telegram_message_ids: list[int]) -> None:
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    UPDATE messages
                    SET status = 'processed', telegram_message_ids = ?, sent_at = ?, error = NULL
                    WHERE chat_id = ? AND message_id = ?
                    """,
                    (json.dumps(telegram_message_ids), _utcnow(), chat_id, message_id),
                )

    def mark_failed(self, chat_id: str, message_id: int, error: str) -> None:
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    """
                    UPDATE messages
                    SET status = 'failed', error = ?, failed_at = ?
                    WHERE chat_id = ? AND message_id = ?
                    """,
                    (error, _utcnow(), chat_id, message_id),
                )

    def get_message(self, chat_id: str, message_id: int) -> MessageRecord:
        self.initialize()
        with closing(self._connect()) as db:
            row = db.execute(
                "SELECT * FROM messages WHERE chat_id = ? AND message_id = ?",
                (chat_id, message_id),
            ).fetchone()
        if row is None:
            raise KeyError(f"message not found: {chat_id}/{message_id}")
        return _record_from_row(row)

    def _update(
        self,
        chat_id: str,
        message_id: int,
        status: str,
        field: str,
        value: str,
        timestamp_field: str,
    ) -> None:
        with closing(self._connect()) as db:
            with db:
                db.execute(
                    f"""
                    UPDATE messages
                    SET status = ?, {field} = ?, {timestamp_field} = ?
                    WHERE chat_id = ? AND message_id = ?
                    """,
                    (status, value, _utcnow(), chat_id, message_id),
                )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self._path)
        db.row_factory = sqlite3.Row
        return db


def _record_from_row(row: sqlite3.Row) -> MessageRecord:
    raw_ids = row["telegram_message_ids"]
    return MessageRecord(
        chat_id=row["chat_id"],
        message_id=int(row["message_id"]),
        title=row["title"],
        message_date=row["message_date"],
        status=row["status"],
        source_path=Path(row["source_path"]) if row["source_path"] else None,
        converted_path=Path(row["converted_path"]) if row["converted_path"] else None,
        notebook_id=row["notebook_id"],
        notebook_url=row["notebook_url"],
        summary=row["summary"],
        podcast_path=Path(row["podcast_path"]) if row["podcast_path"] else None,
        telegram_message_ids=json.loads(raw_ids) if raw_ids else [],
        error=row["error"],
    )


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

