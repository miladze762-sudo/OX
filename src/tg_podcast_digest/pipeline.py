from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import AudioItem, NotebookResult, RunResult
from .state import StateStore


class SourcePort(Protocol):
    async def list_audio(self, max_messages: int) -> list[AudioItem]: ...

    async def download_audio(self, item: AudioItem, download_dir: Path) -> Path: ...


class ConverterPort(Protocol):
    def convert_to_mp3(self, source_path: Path, converted_dir: Path) -> Path: ...


class NotebookPort(Protocol):
    async def create_summary_and_podcast(
        self,
        item: AudioItem,
        mp3_path: Path,
        export_dir: Path,
    ) -> NotebookResult: ...


class SenderPort(Protocol):
    def send_podcast(
        self,
        title: str,
        summary: str,
        podcast_path: Path,
        notebook_url: str | None = None,
    ) -> list[int]: ...


class PodcastPipeline:
    def __init__(
        self,
        source: SourcePort,
        converter: ConverterPort,
        notebook: NotebookPort,
        sender: SenderPort,
        state: StateStore,
        download_dir: Path,
        converted_dir: Path,
        export_dir: Path,
    ) -> None:
        self._source = source
        self._converter = converter
        self._notebook = notebook
        self._sender = sender
        self._state = state
        self._download_dir = download_dir
        self._converted_dir = converted_dir
        self._export_dir = export_dir

    async def run_once(self, dry_run: bool = False, max_messages: int = 10) -> RunResult:
        self._state.initialize()
        items = await self._source.list_audio(max_messages)
        if dry_run:
            return RunResult(dry_run_items=items)

        processed = 0
        skipped = 0
        errors: list[str] = []
        for audio in items:
            if not self._state.claim_message(audio.chat_id, audio.message_id, audio.title, audio.message_date):
                skipped += 1
                continue
            try:
                source_path = await self._source.download_audio(audio, self._download_dir)
                self._state.mark_downloaded(audio.chat_id, audio.message_id, source_path)

                mp3_path = self._converter.convert_to_mp3(source_path, self._converted_dir)
                self._state.mark_converted(audio.chat_id, audio.message_id, mp3_path)

                notebook_result = await self._notebook.create_summary_and_podcast(
                    audio,
                    mp3_path,
                    self._export_dir,
                )
                self._state.mark_notebook_ready(
                    audio.chat_id,
                    audio.message_id,
                    notebook_result.notebook_id,
                    notebook_result.notebook_url,
                )
                self._state.mark_summary_ready(audio.chat_id, audio.message_id, notebook_result.summary)
                self._state.mark_podcast_ready(audio.chat_id, audio.message_id, notebook_result.podcast_path)

                sent_ids = self._sender.send_podcast(
                    audio.title,
                    notebook_result.summary,
                    notebook_result.podcast_path,
                    notebook_result.notebook_url,
                )
                self._state.mark_sent(audio.chat_id, audio.message_id, sent_ids)
                processed += 1
            except Exception as exc:  # noqa: BLE001 - keep one bad audio from stopping the batch.
                message = f"{audio.chat_id}/{audio.message_id}: {exc}"
                errors.append(message)
                self._state.mark_failed(audio.chat_id, audio.message_id, message)
        return RunResult(processed_count=processed, skipped_count=skipped, errors=errors)

