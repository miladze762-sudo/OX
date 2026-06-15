from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AudioItem:
    chat_id: str
    message_id: int
    title: str
    message_date: str | None
    file_name: str | None
    mime_type: str | None


@dataclass(frozen=True)
class NotebookResult:
    notebook_id: str
    notebook_url: str
    summary: str
    podcast_path: Path


@dataclass(frozen=True)
class RunResult:
    processed_count: int = 0
    skipped_count: int = 0
    errors: list[str] = field(default_factory=list)
    dry_run_items: list[AudioItem] = field(default_factory=list)

