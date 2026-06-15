from __future__ import annotations

import re
from pathlib import Path

from .models import AudioItem, NotebookResult


def build_notebook_title(item: AudioItem) -> str:
    date_part = item.message_date or "no-date"
    name_part = item.file_name or item.title or "audio"
    title = f"Telegram Podcast - {date_part} - {item.message_id} - {name_part}"
    title = re.sub(r'[\\/:*?"<>|]+', " - ", title)
    title = re.sub(r"\s+", " ", title).strip(" -")
    return title[:120]


def build_summary_prompt(item: AudioItem) -> str:
    return f"""
Сделай содержательную выжимку аудио "{item.title}" по-русски.

Формат:
1. Главный тезис: 1-2 предложения.
2. Ключевые пункты: 7-10 коротких пунктов.
3. Что важно запомнить: 3-5 практичных выводов.
4. Возможные оговорки: что в аудио звучало как мнение, гипотеза или спорная интерпретация.

Не добавляй факты, которых нет в источнике. Если вывод является интерпретацией, обозначь это.
""".strip()


def build_podcast_prompt(item: AudioItem) -> str:
    return f"""
Сделай русскоязычный audio overview как глубокий подкаст примерно на 20 минут по аудио "{item.title}".
Стиль: живой, спокойный, плотный по смыслу, без воды.
Сохрани фактическую точность, не выдумывай детали, явно отделяй интерпретации от фактов.
""".strip()


class NotebookLMProcessor:
    def __init__(self, storage_path: Path | None = None, wait_timeout: float = 1800.0) -> None:
        self._storage_path = storage_path
        self._wait_timeout = wait_timeout

    async def create_summary_and_podcast(
        self,
        item: AudioItem,
        mp3_path: Path,
        export_dir: Path,
    ) -> NotebookResult:
        try:
            from notebooklm import NotebookLMClient
        except ImportError as exc:
            raise RuntimeError("notebooklm-py is missing. Run: python -m pip install -e .") from exc

        export_dir.mkdir(parents=True, exist_ok=True)
        notebook_title = build_notebook_title(item)
        storage = str(self._storage_path) if self._storage_path else None
        async with NotebookLMClient.from_storage(path=storage, keepalive=300.0) as client:
            notebook = await client.notebooks.create(notebook_title)
            source = await client.sources.add_file(
                notebook.id,
                mp3_path,
                title=item.file_name or mp3_path.name,
                wait=True,
                wait_timeout=600.0,
                upload_timeout=600.0,
            )
            source_id = getattr(source, "id", None)
            source_ids = [source_id] if source_id else None
            if source_ids:
                answer = await client.chat.ask(notebook.id, build_summary_prompt(item), source_ids=source_ids)
            else:
                answer = await client.chat.ask(notebook.id, build_summary_prompt(item))
            status = await client.artifacts.generate_audio(
                notebook.id,
                instructions=build_podcast_prompt(item),
            )
            await client.artifacts.wait_for_completion(
                notebook.id,
                status.task_id,
                timeout=self._wait_timeout,
            )
            podcast_path = export_dir / f"{item.chat_id}_{item.message_id}_notebooklm.mp3"
            downloaded = await client.artifacts.download_audio(notebook.id, str(podcast_path))
            return NotebookResult(
                notebook_id=notebook.id,
                notebook_url=f"https://notebooklm.google.com/notebook/{notebook.id}",
                summary=answer.answer,
                podcast_path=Path(downloaded),
            )

