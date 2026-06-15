import asyncio
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tg_podcast_digest.models import AudioItem, NotebookResult
from tg_podcast_digest.pipeline import PodcastPipeline
from tg_podcast_digest.state import StateStore


class FakeSource:
    def __init__(self, items):
        self.items = items
        self.downloaded = []

    async def list_audio(self, max_messages):
        return self.items[:max_messages]

    async def download_audio(self, item, download_dir):
        path = download_dir / f"{item.message_id}.ogg"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"source")
        self.downloaded.append(item.message_id)
        return path


class FakeConverter:
    def __init__(self):
        self.converted = []

    def convert_to_mp3(self, source_path, converted_dir):
        path = converted_dir / (source_path.stem + ".mp3")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"mp3")
        self.converted.append(source_path)
        return path


class FakeNotebook:
    def __init__(self, tmp):
        self.tmp = Path(tmp)
        self.processed = []

    async def create_summary_and_podcast(self, item, mp3_path, export_dir):
        podcast = export_dir / f"{item.message_id}-podcast.mp3"
        podcast.parent.mkdir(parents=True, exist_ok=True)
        podcast.write_bytes(b"podcast")
        self.processed.append(item.message_id)
        return NotebookResult(
            notebook_id=f"nb-{item.message_id}",
            notebook_url=f"https://notebook/{item.message_id}",
            summary=f"summary {item.message_id}",
            podcast_path=podcast,
        )


class FailingNotebook(FakeNotebook):
    async def create_summary_and_podcast(self, item, mp3_path, export_dir):
        raise RuntimeError("NotebookLM failed")


class FakeSender:
    def __init__(self):
        self.sent = []

    def send_podcast(self, title, summary, podcast_path, notebook_url=None):
        self.sent.append((title, summary, podcast_path, notebook_url))
        return [100, 101]


def item(message_id=1):
    return AudioItem(
        chat_id="chat",
        message_id=message_id,
        title="Episode",
        message_date="2026-06-15",
        file_name="episode.ogg",
        mime_type="audio/ogg",
    )


class PipelineTests(unittest.TestCase):
    def test_dry_run_lists_items_without_side_effects(self):
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = PodcastPipeline(
                source=FakeSource([item(1)]),
                converter=FakeConverter(),
                notebook=FakeNotebook(tmp),
                sender=FakeSender(),
                state=StateStore(Path(tmp) / "state.sqlite3"),
                download_dir=Path(tmp) / "downloads",
                converted_dir=Path(tmp) / "converted",
                export_dir=Path(tmp) / "exports",
            )

            result = asyncio.run(pipeline.run_once(dry_run=True, max_messages=10))

        self.assertEqual([1], [audio.message_id for audio in result.dry_run_items])
        self.assertEqual(0, result.processed_count)

    def test_successful_run_records_state_after_send(self):
        with tempfile.TemporaryDirectory() as tmp:
            sender = FakeSender()
            state = StateStore(Path(tmp) / "state.sqlite3")
            pipeline = PodcastPipeline(
                source=FakeSource([item(2)]),
                converter=FakeConverter(),
                notebook=FakeNotebook(tmp),
                sender=sender,
                state=state,
                download_dir=Path(tmp) / "downloads",
                converted_dir=Path(tmp) / "converted",
                export_dir=Path(tmp) / "exports",
            )

            result = asyncio.run(pipeline.run_once(dry_run=False, max_messages=10))
            record = state.get_message("chat", 2)

        self.assertEqual(1, result.processed_count)
        self.assertEqual("processed", record.status)
        self.assertEqual("nb-2", record.notebook_id)
        self.assertEqual([100, 101], record.telegram_message_ids)
        self.assertEqual("summary 2", sender.sent[0][1])

    def test_failed_run_is_retryable(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = StateStore(Path(tmp) / "state.sqlite3")
            pipeline = PodcastPipeline(
                source=FakeSource([item(3)]),
                converter=FakeConverter(),
                notebook=FailingNotebook(tmp),
                sender=FakeSender(),
                state=state,
                download_dir=Path(tmp) / "downloads",
                converted_dir=Path(tmp) / "converted",
                export_dir=Path(tmp) / "exports",
            )

            result = asyncio.run(pipeline.run_once(dry_run=False, max_messages=10))
            self.assertEqual(1, len(result.errors))
            self.assertTrue(state.claim_message("chat", 3, "Episode", "2026-06-15"))


if __name__ == "__main__":
    unittest.main()

